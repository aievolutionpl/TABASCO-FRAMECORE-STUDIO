"""Licencje, lokalność, integralność i współdzielone operacje Creator Pack."""
from pathlib import Path
import pytest
from framecore.api import API
from framecore.backgrounds import catalog as backgrounds
from framecore.composition import compile_project
from framecore.library import catalog, manifest, checked_file
from framecore.model import EditorError, validate
from framecore.render import RenderJobs
from framecore.store import Store
from framecore.templates import catalog as templates

ROOT=Path(__file__).resolve().parents[1]


def test_pack_integrity_license_and_local_fonts():
    pack=manifest()
    assert len(pack['fonts'])==8
    assert len(catalog('icon'))==60
    assert len(catalog('illustration'))==24
    for item in pack['fonts']+pack['assets']:
        assert len(item['commit'])==40
        assert checked_file(item)==(ROOT/item['file']).read_bytes()
        assert (ROOT/item['licenseFile']).is_file()
        assert item['license'] in {'MIT','ISC/MIT','OFL-1.1'}
    assert all(f['polish'] for f in pack['fonts'])
    css=(ROOT/'framecore/static/library/fonts.css').read_text()
    assert 'http' not in css
    assert all(f['id']+'.ttf' in css for f in pack['fonts'])


@pytest.mark.parametrize('format',['9:16','4:5','1:1','16:9'])
def test_every_template_uses_distinct_look_and_editable_local_assets(tmp_path,format):
    store=Store(tmp_path/'projects');looks=set()
    for t in templates():
        state=store.create(t['name'],format,6);pid=state['project']['id']
        state=store.execute(pid,'apply_template',{'template_id':t['id']},0)
        p=state['project'];validate(p)
        assert len(p['scenes'])==6
        assert len([e for e in p['elements'] if e['type']=='text'])==6
        assert all((store.directory(pid)/a['file']).is_file() for a in p['assets'])
        html=compile_project(p)
        assert 'data:font/ttf;base64,' in html and 'fonts.googleapis' not in html
        looks.add((p['brand']['font'],p['canvas']['backgroundPreset']))
        assert store.execute(pid,'undo',{},1)['project']['elements']==[]
    assert len(looks)==12


def test_agent_library_and_background_proposal_is_one_undo(tmp_path):
    store=Store(tmp_path/'projects');api=API(store,RenderJobs(store))
    p=store.create('Materiały')['project'];pid=p['id']
    assert len(api.call('list_library')['assets'])==84
    assert len(api.call('list_backgrounds')['backgrounds'])==24
    commands=[{'name':'add_library_asset','args':{'asset_id':'fluent-rocket'}},
              {'name':'add_icon','args':{'icon_id':'lucide-leaf'}},
              {'name':'set_background','args':{'background_id':'aurora-breath'}}]
    args={'project_id':pid,'expected_revision':0}
    state=api.call('propose_changes',{**args,'commands':commands})
    proposal=state['proposals'][-1]
    assert state['project']==p
    state=api.call('apply_proposal',{**args,'proposal_id':proposal['id']})
    assert state['project']['assets']==proposal['projectAfter']['assets']
    assert len(state['project']['elements'])==2
    assert all((store.directory(pid)/a['file']).is_file() for a in state['project']['assets'])
    undone=api.call('undo',{**args,'expected_revision':1})['project']
    assert undone['elements']==[] and not undone['canvas'].get('backgroundPreset')
    before=store.read(pid)
    for name,arguments in [('add_library_asset',{'asset_id':'../../secret'}),('set_background',{'background_id':'url(https://example.com)'})]:
        with pytest.raises(EditorError):api.call(name,{**args,'expected_revision':2,**arguments})
    for property,value in [('style.fontFamily',42),('style.fontFamily','\n'),('style.fontWeight',0)]:
        with pytest.raises(EditorError):store.execute(pid,'add_text',{'text':'Błąd fontu','style':{property[6:]:value}},2)
    assert store.read(pid)==before


def test_showcase_copy_preserves_original_and_existing_projects(tmp_path):
    from framecore.sample import create_creator_pack
    source=ROOT/'examples/creator-pack/project.json';before=source.read_bytes()
    store=Store(tmp_path/'projects')
    first=create_creator_pack(store);second=create_creator_pack(store)
    assert first['project']['id']!=second['project']['id']
    assert store.read(first['project']['id'])==first
    assert source.read_bytes()==before
    assert first['project']['revision']==0 and first['history']==[]
    assert all((store.directory(first['project']['id'])/a['file']).is_file() for a in first['project']['assets'])
