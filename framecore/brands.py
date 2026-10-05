"""Versioned company brains, image libraries and immutable project snapshots."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlparse

from PIL import Image
from vstudio.locking import atomic_write, file_lock
from .model import EditorError, identifier, now, uid

TEXT_FIELDS = ('name', 'website', 'industry', 'about', 'offer', 'audience', 'positioning', 'tone',
               'cta', 'guidelines', 'logoRules', 'motionRules', 'restrictions', 'researchNotes')
DEFAULT = {**{k: '' for k in TEXT_FIELDS}, 'name': 'Nowa marka', 'businessType': 'services',
           'colors': {'background': '#101415', 'text': '#f5f3ec', 'accent': '#ff4d24'},
           'font': 'Manrope', 'sources': [], 'products': []}


def url(value):
    if value and (urlparse(value).scheme not in {'http', 'https'} or not urlparse(value).hostname):
        raise EditorError('Adres źródła lub firmy musi zaczynać się od https:// albo http://')
    return value


def validate_profile(data):
    if not isinstance(data, dict) or set(data) - set(DEFAULT):
        raise EditorError('Nieznane pola profilu marki')
    result = deepcopy(DEFAULT)
    for k, v in data.items():
        if k in TEXT_FIELDS or k == 'font':
            if not isinstance(v, str) or len(v) > (200 if k in {'name', 'font'} else 12000):
                raise EditorError(f'Nieprawidłowe pole: {k}')
            result[k] = v.strip()
        else:
            result[k] = deepcopy(v)
    if not result['name']:
        raise EditorError('Podaj nazwę firmy')
    url(result['website'])
    if result['businessType'] not in {'services', 'products', 'both'}:
        raise EditorError('Wybierz usługi, produkty albo ofertę mieszaną')
    if not isinstance(result['colors'], dict) or set(result['colors']) != {'background', 'text', 'accent'} or any(
        not isinstance(v, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', v) for v in result['colors'].values()):
        raise EditorError('Trzy kolory muszą mieć postać #RRGGBB')
    from .library import fonts
    if result['font'] not in {f['family'] for f in fonts()} | {'Arial', 'Georgia', 'Verdana', 'Times New Roman'}:
        raise EditorError('Wybierz font dostępny lokalnie w studiu')
    for field, keys in [('sources', {'url', 'note'}), ('products', {'name', 'description', 'url'})]:
        entries = result[field]
        if not isinstance(entries, list) or len(entries) > 60:
            raise EditorError(f'{field}: maksymalnie 60 pozycji')
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != keys or any(not isinstance(v, str) or len(v) > 4000 for v in entry.values()):
                raise EditorError(f'Nieprawidłowa pozycja: {field}')
            url(entry['url'])
    return result


class BrandLibrary:
    def __init__(self, store):
        self.store = store
        self.root = store.root / '_brands'
        self.root.mkdir(exist_ok=True)

    def directory(self, bid):
        identifier(bid)
        return self.root / bid

    def _read(self, bid):
        path = self.directory(bid) / 'profile.json'
        if not path.is_file():
            raise EditorError('Nie znaleziono marki', 'not_found')
        return json.loads(path.read_text(encoding='utf-8'))

    def get(self, bid):
        with file_lock(self.root / '.lock'):
            return self._read(bid)

    def list(self):
        with file_lock(self.root / '.lock'):
            profiles = [json.loads(p.read_text(encoding='utf-8')) for p in self.root.glob('*/profile.json')]
            return {'profiles': sorted(profiles, key=lambda b: b['name'].lower())}

    def _write(self, profile):
        profile['updatedAt'] = now()
        atomic_write(self.directory(profile['id']) / 'profile.json', json.dumps(profile, ensure_ascii=False, indent=2))
        return deepcopy(profile)

    def save(self, data, bid=None, version=None):
        fields = validate_profile(data)
        with file_lock(self.root / '.lock'):
            if bid:
                before = self._read(bid)
                self._version(before, version)
                profile = {**before, **fields, 'version': before['version'] + 1}
            else:
                bid = uid('brand')
                (self.directory(bid) / 'assets').mkdir(parents=True)
                profile = {**fields, 'id': bid, 'version': 1, 'createdAt': now(), 'assets': []}
            return self._write(profile)

    @staticmethod
    def _version(profile, version):
        if isinstance(version, bool) or not isinstance(version, int) or version != profile['version']:
            raise EditorError('Profil zmienił się; wczytaj aktualną wersję', 'revision_conflict')

    def delete(self, bid, version):
        with file_lock(self.root / '.lock'):
            self._version(self._read(bid), version)
            shutil.rmtree(self.directory(bid))
            return {'deleted': bid}

    def upload(self, bid, version, data, filename, role):
        suffix = Path(filename).suffix.lower()
        if suffix not in {'.png', '.jpg', '.jpeg', '.webp'} or not data or len(data) > 20_000_000 or role not in {'logo', 'reference', 'product'}:
            raise EditorError('Dodaj PNG, JPG lub WebP do 20 MB jako logo, referencję albo produkt')
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {'PNG', 'JPEG', 'WEBP'}:
                    raise EditorError('Dozwolone są tylko PNG, JPG i WebP')
                if image.width * image.height > 40_000_000:
                    raise EditorError('Obraz przekracza 40 megapikseli')
                image.verify()
        except EditorError:
            raise
        except Exception:
            raise EditorError('Plik nie zawiera poprawnego obrazu')
        with file_lock(self.root / '.lock'):
            profile = self._read(bid)
            self._version(profile, version)
            if len(profile['assets']) >= 60:
                raise EditorError('Profil może zawierać najwyżej 60 obrazów')
            aid = uid('brandasset')
            file = f'assets/{aid}{suffix}'
            a = {'id': aid, 'name': Path(filename).name[:200], 'file': file, 'role': role,
                 'sha256': hashlib.sha256(data).hexdigest(), 'license': 'user_provided'}
            path = self.directory(bid) / file
            path.write_bytes(data)
            profile['assets'].append(a)
            profile['version'] += 1
            try:
                return self._write(profile)
            except Exception:
                path.unlink(missing_ok=True)
                raise

    def remove_asset(self, bid, version, aid):
        with file_lock(self.root / '.lock'):
            profile = self._read(bid)
            self._version(profile, version)
            asset = next((a for a in profile['assets'] if a['id'] == aid), None)
            if not asset:
                raise EditorError('Nie znaleziono materiału marki')
            profile['assets'].remove(asset)
            profile['version'] += 1
            result = self._write(profile)
            (self.directory(bid) / asset['file']).unlink(missing_ok=True)
            return result

    def apply(self, bid, version, pid, revision, restyle=False, actor='human'):
        if not isinstance(restyle, bool):
            raise EditorError('restyle musi być wartością logiczną')
        copied = []
        with file_lock(self.root / '.lock'):
            profile = self._read(bid)
            self._version(profile, version)
            self.store.read(pid)
            assets = []
            try:
                for a in profile['assets']:
                    source = self.directory(bid) / a['file']
                    if hashlib.sha256(source.read_bytes()).hexdigest() != a['sha256']:
                        raise EditorError('Materiał marki zmienił zawartość; wgraj go ponownie')
                    aid = uid('asset')
                    file = f'assets/{aid}{source.suffix}'
                    target = self.store.directory(pid) / file
                    shutil.copy2(source, target)
                    copied.append(target)
                    if hashlib.sha256(target.read_bytes()).hexdigest() != a['sha256']:
                        raise EditorError('Materiał marki zmienił zawartość podczas kopiowania')
                    with Image.open(source) as image:
                        mime = Image.MIME.get(image.format, 'image/png')
                    assets.append({'id': aid, 'name': a['name'], 'kind': 'image', 'file': file,
                                   'mime': mime,
                                   'duration': None, 'hasAudio': False, 'role': a['role'],
                                   'license': a['license'], 'provenance': {'source': 'brand_profile', 'brand_id': bid,
                                                                         'brand_version': version, 'sha256': a['sha256']}})
                snapshot = deepcopy(profile)
                snapshot['assets'] = deepcopy(assets)
                snapshot['snapshotAt'] = now()
                brand = {'name': profile['name'], 'colors': profile['colors'], 'font': profile['font'],
                         'logoAssetId': next((a['id'] for a in assets if a['role'] == 'logo'), None)}
                return self.store.execute(pid, 'attach_brand_snapshot', {'snapshot': snapshot, 'brand': brand,
                    'assets': assets, 'restyle': restyle, 'description': 'Wybrano profil marki: ' + profile['name']}, revision, actor)
            except Exception:
                for file in copied:
                    file.unlink(missing_ok=True)
                raise
