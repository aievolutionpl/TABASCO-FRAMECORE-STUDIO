"""Audytowane, lokalne materiały. Zamknięty katalog, licencje i sumy SHA-256."""
import base64
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from .model import EditorError, uid

STATIC = Path(__file__).parent / 'static'
ROOT = STATIC / 'icons'
ICONS = {'sparkle':'Iskra','lightning':'Energia','film-strip':'Film','robot':'Agent AI',
         'music-notes':'Muzyka','waveform':'Dźwięk','palette':'Paleta','shapes':'Kształty',
         'check':'Gotowe','arrow-right':'Dalej','images':'Obrazy','scissors':'Montaż'}


@lru_cache(maxsize=1)
def manifest():
    return json.loads((STATIC / 'library/catalog.json').read_text(encoding='utf-8'))


def checked_file(entry):
    path = (STATIC.parent.parent / entry['file']).resolve()
    if not path.is_relative_to((STATIC / 'library').resolve()) or not path.is_file():
        raise EditorError('Nieprawidłowy plik biblioteki')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise EditorError('Plik biblioteki nie zgadza się z sumą SHA-256')
    return data


def catalog(kind=None):
    old = [{'id':k,'name':v,'kind':'icon','collection':'Phosphor','license':'MIT',
            'preview':f'/static/icons/{k}.svg','tags':[v.lower(),k,'phosphor']} for k,v in ICONS.items()]
    items = old + [{**a,'preview':'/static/'+a['file'].split('/static/',1)[1]} for a in manifest()['assets']]
    return [a for a in items if kind is None or a['kind']==kind]


def fonts():
    return [{k:v for k,v in f.items() if k!='file'} for f in manifest()['fonts']]


def font_css(project):
    used = {e['style']['fontFamily'] for e in project['elements'] if e['type'] in {'text','caption'}}
    rules = []
    for f in manifest()['fonts']:
        if f['family'] in used:
            encoded = base64.b64encode(checked_file(f)).decode('ascii')
            weights = ' '.join(map(str,f['weight']))
            rules.append('@font-face{font-family:'+json.dumps(f['family'])+';src:url(data:font/ttf;base64,'+encoded+') format("truetype");font-weight:'+weights+';font-style:normal;font-display:block}')
    return '\n'.join(rules)


def library_asset(asset_id):
    if asset_id in ICONS:
        return icon_asset(asset_id)
    a = next((a for a in manifest()['assets'] if a['id']==asset_id),None)
    if a is None:
        raise EditorError('Nieznany materiał biblioteki')
    aid = uid('asset'); suffix = Path(a['file']).suffix
    return {'id':aid,'name':a['name'],'kind':'image','file':f'assets/{aid}{suffix}',
            'mime':'image/svg+xml' if suffix=='.svg' else 'image/png','duration':None,
            'role':'icon' if a['kind']=='icon' else 'illustration','license':a['license'],
            'provenance':{'source':'framecore_builtin','library_id':asset_id,'version':manifest()['version'],
                          'collection':a['collection'],'sha256':a['sha256'],'upstream':a['source'],'commit':a['commit']}}


def icon_asset(icon_id):
    if icon_id not in ICONS:
        if not any(a['id']==icon_id and a['kind']=='icon' for a in manifest()['assets']):
            raise EditorError('Nieznana ikona')
        return library_asset(icon_id)
    aid=uid('asset')
    return {'id':aid,'name':ICONS[icon_id],'kind':'image','file':f'assets/{aid}.svg','mime':'image/svg+xml',
            'duration':None,'role':'icon','license':'MIT',
            'provenance':{'source':'phosphor_builtin','icon_id':icon_id,'version':'2.1.1'}}


def materialize(project, directory):
    for a in project['assets']:
        provenance=a.get('provenance',{});source=provenance.get('source')
        if source not in {'phosphor_builtin','framecore_builtin'}:
            continue
        if source=='phosphor_builtin':
            key=provenance.get('icon_id')
            if key not in ICONS: raise EditorError('Nieznana ikona biblioteki')
            data=(ROOT/(key+'.svg')).read_bytes()
        else:
            entry=next((e for e in manifest()['assets'] if e['id']==provenance.get('library_id')),None)
            if entry is None: raise EditorError('Nieznany materiał biblioteki')
            data=checked_file(entry)
            if Path(a['file']).suffix != Path(entry['file']).suffix:
                raise EditorError('Nieprawidłowy typ pliku biblioteki')
        path=directory/a['file']
        if not path.exists(): path.write_bytes(data)
