"""Editing transactions protect media bounds, locked tracks and shared history."""
from copy import deepcopy
import pytest
from framecore.api import API
from framecore.model import EditorError
from framecore.store import Store

@pytest.fixture
def edit(tmp_path):
    store=Store(tmp_path/'projects');pid=store.create('Montaż',duration=12)['project']['id']
    api=API(store,None)
    def call(tool,**args):
        return api.call(tool,{'project_id':pid,'expected_revision':store.read(pid)['project']['revision'],**args})
    return store,pid,api,call


def test_track_local_ripple_gaps_undo_and_agent_proposal(edit):
    store,pid,api,call=edit
    for start in [1,4,8]:call('add_text',text=f'Klip {start}',start=start,duration=2,motion=None)
    s=call('add_shape',start=5,duration=2)
    before=deepcopy(s['project']);first=before['elements'][0];other=before['elements'][-1]
    proposal=call('propose_changes',commands=[{'name':'ripple_delete','args':{'element_id':first['id']}}],description='Usuń pierwszy')
    assert store.read(pid)['project']==before
    s=call('apply_proposal',proposal_id=proposal['proposals'][-1]['id'])
    assert [e['start'] for e in s['project']['elements'] if e['type']=='text']==[2,6]
    assert s['project']['elements'][-1]==other and s['project']['duration']==12
    s=call('undo');assert s['project']['elements']==before['elements']
    s=call('close_track_gaps',track_id=first['trackId'])
    assert [e['start'] for e in s['project']['elements'] if e['type']=='text']==[0,2,4]
    assert s['project']['elements'][-1]==other
    call('set_track',track_id=first['trackId'],property='locked',value=True)
    frozen=store.read(pid)
    for name,args in [('close_track_gaps',{'track_id':first['trackId']}),('ripple_delete',{'element_id':first['id']})]:
        with pytest.raises(EditorError,match='[Zz]ablokowan|odblokowan'):call(name,**args)
        assert store.read(pid)==frozen


def test_overlap_rejected_without_editing_any_clip(edit):
    store,pid,api,call=edit
    call('add_text',text='A',start=0,duration=4)
    s=call('add_text',text='B',start=3,duration=3);e=s['project']['elements'][0]
    before=store.read(pid)
    for name,args in [('ripple_delete',{'element_id':e['id']}),('close_track_gaps',{'track_id':e['trackId']})]:
        with pytest.raises(EditorError,match='nachodzą'):call(name,**args)
        assert store.read(pid)==before


def test_slip_preserves_edit_and_checks_source_bounds(edit):
    store,pid,api,call=edit
    asset={'id':'asset_test','kind':'video','name':'Nagranie','file':'assets/test.mp4','mime':'video/mp4','duration':10}
    s=store.execute(pid,'add_asset',{'asset':asset},0)
    s=call('add_video',assetId=asset['id'],start=3,duration=4)
    eid=s['project']['elements'][0]['id'];before=deepcopy(s['project']['elements'][0])
    s=call('slip_clip',element_id=eid,source_start=6)
    assert s['project']['elements'][0]=={**before,'sourceStart':6}
    frozen=store.read(pid)
    for value in [-.01,6.01,float('nan')]:
        with pytest.raises(EditorError):call('slip_clip',element_id=eid,source_start=value)
        assert store.read(pid)==frozen
    s=call('undo');assert s['project']['elements'][0]==before


def test_presets_shared_with_mcp_and_invalid_fx_atomic(edit):
    store,pid,api,call=edit
    presets=api.call('list_editing_presets',{})
    assert len(presets['transitions'])==11 and len(presets['clipLooks'])==7
    tools={t['name']:t for t in api.tools()}
    assert tools['list_editing_presets']['inputSchema']['required']==[]
    assert tools['ripple_delete']['annotations']['destructiveHint']
    for name in ['set_clip_fx','set_scene_transition','slip_clip','close_track_gaps','ripple_delete']:
        assert 'expected_revision' in tools[name]['inputSchema']['required']
    s=call('add_text',text='Efekt',duration=3);eid=s['project']['elements'][0]['id']
    call('set_clip_fx',element_id=eid,fx={'look':'noir','strength':.5})
    call('add_scene',name='A',start=0,duration=3)
    s=call('add_scene',name='B',start=3,duration=3);sid=s['project']['scenes'][-1]['id']
    call('set_scene_transition',scene_id=sid,transition={'id':'iris','duration':.8})
    frozen=store.read(pid)
    for name,args in [('set_clip_fx',{'element_id':eid,'fx':{'look':'script'}}),
                      ('set_clip_fx',{'element_id':eid,'fx':{'look':'warm','strength':2}}),
                      ('set_scene_transition',{'scene_id':sid,'transition':{'id':'iris','duration':0}})]:
        with pytest.raises(EditorError):call(name,**args)
        assert store.read(pid)==frozen
    s=call('set_scene_transition',scene_id=sid,transition=None)
    assert 'transition' not in s['project']['scenes'][-1]

@pytest.mark.browser
def test_effects_render_pixels_and_repeatable_seek(tmp_path):
    import io,shutil
    from PIL import Image,ImageChops
    from playwright.sync_api import sync_playwright
    from framecore.composition import compile_project
    from framecore.editing import TRANSITION_NAMES
    from framecore.server import start_background
    store=Store(tmp_path/'render-projects');pid=store.create('Efekty',duration=4)['project']['id']
    def call(tool,**args):return store.execute(pid,tool,args,store.read(pid)['project']['revision'])
    call('add_shape',start=0,duration=4,x=0,y=0,width=1920,height=1920,style={'background':'#ea4b2a','radius':0},motion=None)
    call('add_scene',name='A',start=0,duration=2)
    call('add_scene',name='B',start=2,duration=2)
    p=store.read(pid)['project'];p['canvas'].update(width=320,height=180)
    srv,_=start_background(store)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(**({'executable_path':shutil.which('chromium')} if shutil.which('chromium') else {}))
            page=browser.new_page(viewport={'width':320,'height':180});errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{srv.server_port}/composition/{pid}')
            def load():
                page.set_content(compile_project(p));page.evaluate('window.__ready');page.evaluate('window.seek(2)')
            def shot():return page.screenshot()
            load();baseline=Image.open(io.BytesIO(shot())).convert('RGB')
            for tid in TRANSITION_NAMES.keys()-{'none'}:
                # Override must work even with the global default explicitly disabled.
                p['canvas']['fx']={'transition':'none'}
                p['scenes'][1]['transition']={'id':tid,'duration':.8}
                load();expected=shot();actual=Image.open(io.BytesIO(expected)).convert('RGB')
                assert ImageChops.difference(actual,baseline).getbbox(),tid
                page.evaluate('window.seek(.1)');page.evaluate('window.seek(3.5)');page.evaluate('window.seek(2)')
                assert shot()==expected,tid
                page.evaluate('window.seek(.1)')
                assert page.locator('.fc-stage').evaluate('el=>el.style.transform')=='none'
            p['scenes'][1].pop('transition')
            p['elements'][0]['clipFx']={'look':'noir','strength':1};load()
            pixel=Image.open(io.BytesIO(shot())).convert('RGB').getpixel((160,90))
            assert max(pixel)-min(pixel)<=1
            p['elements'][0]['clipFx']['strength']=0;load()
            assert Image.open(io.BytesIO(shot())).convert('RGB').getpixel((160,90))==baseline.getpixel((160,90))
            assert errors==[]
            browser.close()
    finally:srv.shutdown();srv.server_close()


@pytest.mark.browser
def test_editor_effects_scene_override_and_timeline_tools(tmp_path):
    import shutil
    from playwright.sync_api import sync_playwright
    from framecore.server import start_background
    store=Store(tmp_path/'ui-projects');pid=store.create('Timeline',duration=10)['project']['id']
    def call(tool,**args):return store.execute(pid,tool,args,store.read(pid)['project']['revision'])
    call('add_text',text='Pierwszy',start=1,duration=2,motion=None)
    call('add_text',text='Drugi',start=5,duration=2,motion=None)
    call('add_scene',name='Scena A',start=0,duration=5)
    s=call('add_scene',name='Scena B',start=5,duration=5);sid=s['project']['scenes'][1]['id']
    first,second=[e['id'] for e in s['project']['elements']]
    srv,_=start_background(store);errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(**({'executable_path':shutil.which('chromium')} if shutil.which('chromium') else {}))
            page=browser.new_page(viewport={'width':1512,'height':982})
            page.add_init_script("localStorage.setItem('framecore-onboarding-v2','done')")
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{srv.server_port}')
            page.wait_for_function('document.querySelector("#player").ready')
            page.click(f'[data-clip="{first}"]');page.click('[data-tab="Effects"]')
            lib=page.locator('#libraryContent')
            lib.locator('[data-clip-look="noir"]').click()
            lib.locator('[data-clip-look="noir"][aria-pressed="true"]').wait_for()
            assert store.read(pid)['project']['elements'][0]['clipFx']=={'look':'noir','strength':1}
            lib.locator('[data-clip-strength]').fill('0.5');lib.locator('[data-clip-strength]').dispatch_event('change')
            page.wait_for_function('document.querySelector("#libraryContent [data-clip-strength]").value==="0.5"')
            lib.locator('[data-scene-transition="iris"]').click()
            lib.locator('[data-scene-transition="iris"][aria-pressed="true"]').wait_for()
            assert store.read(pid)['project']['scenes'][1]['transition']['id']=='iris'
            lib.locator('[data-scene-transition-duration]').fill('.8');lib.locator('[data-scene-transition-duration]').press('Tab')
            page.wait_for_function('document.querySelector("[data-scene-transition-duration]").value==="0.8"')
            lib.locator('[data-preview-transition]').click()
            page.wait_for_function('document.querySelector("#play").getAttribute("aria-label")=="Pauza"')
            page.wait_for_function('document.querySelector("#play").getAttribute("aria-label")==="Odtwarzaj"',timeout=10000)
            page.screenshot(path=str(tmp_path/'effects-editor.png'))
            lib.locator('[data-reset-transition]').click()
            page.wait_for_function('!document.querySelector("[data-scene-transition=iris]").classList.contains("active")')
            assert 'transition' not in store.read(pid)['project']['scenes'][1]
            page.click('[data-edit="timeline-tools"]')
            page.locator('#modalContent [data-edit="close-gaps"]').click()
            page.wait_for_function('document.querySelectorAll(".clip.text")[0].style.left==="0%"')
            assert [e['start'] for e in store.read(pid)['project']['elements']]==[0,2]
            page.click('#undo');page.wait_for_function('document.querySelectorAll(".clip.text")[0].style.left==="10%"')
            page.click('[data-edit="timeline-tools"]');page.locator('#modalContent [data-edit="ripple-delete"]').click()
            page.wait_for_function('document.querySelectorAll(".clip.text").length===1')
            assert store.read(pid)['project']['elements'][0]['id']==second
            assert store.read(pid)['project']['elements'][0]['start']==3
            page.click('#undo');page.wait_for_function('document.querySelectorAll(".clip.text").length===2')
            page.set_viewport_size({'width':390,'height':844})
            page.click('[data-tab="Effects"]')
            assert page.locator('.library[data-panel-open]').is_visible()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(tmp_path/'effects-mobile.png'))
            assert errors==[]
            browser.close()
    finally:srv.shutdown();srv.server_close()
