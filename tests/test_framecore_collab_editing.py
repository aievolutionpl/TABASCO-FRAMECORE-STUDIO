from copy import deepcopy
import io
import shutil
import time
import subprocess
from pathlib import Path
import pytest
from PIL import Image
from playwright.sync_api import sync_playwright,expect
from framecore.api import API
from framecore.model import EditorError
from framecore.server import import_asset,start_background
from framecore.store import Store
from framecore.render import RenderJobs


def image(color):
    out=io.BytesIO();Image.new('RGB',(80,60),color).save(out,'PNG');return out.getvalue()


def setup(tmp_path):
    store=Store(tmp_path/'projects');pid=store.create('Wspólna edycja','16:9',14)['project']['id']
    a=import_asset(store,pid,image('red'),'A.png')['project']['assets'][-1]['id']
    b=import_asset(store,pid,image('blue'),'B.png')['project']['assets'][-1]['id']
    store.execute(pid,'add_image',{'assetId':a,'start':1,'duration':5,'x':100,'width':300,'motion':{'id':'float','duration':.8}},2)
    e=store.read(pid)['project']['elements'][0]
    store.execute(pid,'set_keyframes',{'element_id':e['id'],'keyframes':[{'property':'x','time':0,'value':100},{'property':'x','time':5,'value':300}]},3)
    return store,API(store,RenderJobs(store)),pid,a,b,e['id']


def edit(api,pid,operation,**args):
    return api.call(operation,{'project_id':pid,'expected_revision':api.store.read(pid)['project']['revision'],**args})


def test_replace_preserves_geometry_motion_history_and_agent_proposal(tmp_path):
    store,api,pid,a,b,eid=setup(tmp_path);before=deepcopy(store.read(pid)['project']['elements'][0])
    result=edit(api,pid,'replace_clip_asset',element_id=eid,asset_id=b)
    after=result['project']['elements'][0]
    assert after=={**before,'assetId':b,'sourceStart':0}
    assert result['history'][-1]['commands'][0]['name']=='replace_clip_asset'
    undo=edit(api,pid,'undo');assert undo['project']['elements'][0]==before
    proposal=edit(api,pid,'propose_changes',description='Agent wybiera zdjęcie',commands=[{'name':'replace_clip_asset','args':{'element_id':eid,'asset_id':b}}])['proposals'][-1]
    edit(api,pid,'apply_proposal',proposal_id=proposal['id'])
    assert store.read(pid)['project']['elements'][0]['assetId']==b
    edit(api,pid,'set_track',track_id='image',property='locked',value=True);snapshot=store.read(pid)
    with pytest.raises(EditorError,match='zablokowana'):edit(api,pid,'replace_clip_asset',element_id=eid,asset_id=a)
    assert store.read(pid)==snapshot


def test_media_kinds_short_sources_and_tracks(tmp_path):
    store,api,pid,a,b,eid=setup(tmp_path)
    path=Path(__file__).parents[1]/'assets/framecore-production-demo.mp4'
    video=import_asset(store,pid,path.read_bytes(),'film.mp4')['project']['assets'][-1]
    edit(api,pid,'replace_clip_asset',element_id=eid,asset_id=video['id'])
    e=store.read(pid)['project']['elements'][0];assert e['type']=='video' and e['trackId']=='image'
    edit(api,pid,'trim_clip',element_id=eid,start=1,duration=2)
    short_file=tmp_path/'short.mp4'
    subprocess.run(['ffmpeg','-y','-i',str(path),'-t','1','-an','-vf','scale=160:90','-c:v','libx264','-preset','ultrafast',str(short_file)],capture_output=True,check=True)
    short=import_asset(store,pid,short_file.read_bytes(),'short.mp4')['project']['assets'][-1]
    edit(api,pid,'replace_clip_asset',element_id=eid,asset_id=b)
    edit(api,pid,'trim_clip',element_id=eid,start=1,duration=3)
    before=store.read(pid)
    with pytest.raises(EditorError,match='krótsze'):edit(api,pid,'replace_clip_asset',element_id=eid,asset_id=short['id'])
    assert store.read(pid)==before
    fitted=edit(api,pid,'replace_clip_asset',element_id=eid,asset_id=short['id'],fit_source=True)['project']['elements'][0]
    assert fitted['duration']==short['duration'] and fitted['sourceStart']==0
    state=edit(api,pid,'add_track',kind='video',name='B-roll');track=state['project']['tracks'][-1]['id']
    edit(api,pid,'move_clip',element_id=eid,start=4,track_id=track)
    with pytest.raises(EditorError):edit(api,pid,'move_clip',element_id=eid,start=4,track_id='text')
    edit(api,pid,'set_track',track_id=track,property='locked',value=True)
    assert store.read(pid)['project']['elements'][0]['trackId']==track


def test_story_plan_validation_undo_and_shared_context(tmp_path):
    store,api,pid,a,b,eid=setup(tmp_path)
    brief={'topic':'Współpraca z agentem','coreIdea':'Człowiek poprawia wynik na wspólnej osi czasu.',
           'openingQuestion':'Kto robi ostatni montaż?','audience':'Początkujący','misconception':'Agent kończy pracę za człowieka.'}
    plan=api.call('plan_visual_lesson',{'project_id':pid,'brief':brief,'duration':14})
    assert len(plan['scenes'])==7 and plan['status']=='editable_starter'
    before=store.read(pid)
    with pytest.raises(EditorError):edit(api,pid,'assemble_visual_lesson',brief=brief)
    assert store.read(pid)==before
    result=edit(api,pid,'assemble_visual_lesson',brief=brief,scenes=plan['scenes'],duration=14,replace=True)
    p=result['project'];assert len(p['scenes'])==7 and len(p['elements'])==21 and p['canvas']['fps']==24
    assert p['production']['requireReview'] and store.context(pid)['lesson']==brief
    assert api.call('get_lesson_status',{'project_id':pid})['issues']
    scene=p['scenes'][0]['id']
    edit(api,pid,'set_scene_learning',scene_id=scene,lesson={'narration':'Ostatni montaż należy do Ciebie.','visual':'Ta sama oś czasu w dwóch rękach.','transition':'Wskaźnik przechodzi w następny krok.'})
    assert store.read(pid)['project']['scenes'][0]['lesson']['narration'].startswith('Ostatni')
    snapshot=store.read(pid)
    with pytest.raises(EditorError):edit(api,pid,'set_scene_learning',scene_id=scene,lesson={'runShell':'bad'})
    assert store.read(pid)==snapshot
    edit(api,pid,'undo');undo=edit(api,pid,'undo');assert undo['project']['elements']==before['project']['elements']
    tools={t['name']:t for t in api.tools()}
    assert tools['get_storytelling_playbook']['inputSchema']['required']==[]
    assert 'asset_id' in tools['replace_clip_asset']['inputSchema']['required']


def test_lesson_keeps_company_brain_visual_guidelines(tmp_path):
    from framecore.brands import BrandLibrary,DEFAULT
    store,api,pid,a,b,eid=setup(tmp_path)
    lib=BrandLibrary(store)
    profile=lib.save({**DEFAULT,'name':'Klient','font':'DM Sans','colors':{'background':'#102025','text':'#ffffee','accent':'#55cccc'}})
    lib.apply(profile['id'],1,pid,store.read(pid)['project']['revision'],True)
    snapshot=store.read(pid)['project']['brandProfile']
    result=edit(api,pid,'assemble_visual_lesson',brief={'topic':'Usługa','coreIdea':'Wyjaśniamy zakres usługi.'},replace=True)
    p=result['project'];assert p['brand']['font']=='DM Sans' and p['canvas']['background']=='#102025'
    assert p['brandProfile']==snapshot and all(e['style']['fontFamily']=='DM Sans' for e in p['elements'])


@pytest.mark.browser
def test_capcut_style_manual_media_and_editable_story(tmp_path):
    store,api,pid,a,b,eid=setup(tmp_path);srv,_=start_background(store);errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'))
            page=browser.new_page(viewport={'width':1512,'height':982});page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{srv.server_port}');page.wait_for_function('document.querySelector("#player").ready')
            page.locator(f'[data-clip="{eid}"]').click();page.click('[data-edit="replace"]')
            page.select_option('#replacementAsset',b);page.click('[data-edit="apply-replace"]');page.locator('#modal').wait_for(state='hidden')
            assert store.read(pid)['project']['elements'][0]['assetId']==b
            assert page.locator('.clip-thumbnail').count()==1
            page.drag_and_drop(f'[data-asset="{a}"]',f'[data-clip="{eid}"]')
            page.wait_for_function("async pid=>(await(await fetch('/api/project/'+pid)).json()).project.elements[0].assetId==='"+a+"'",arg=pid)
            page.click('[data-edit="replace-file"]')
            page.locator('#replaceFile').set_input_files({'name':'Nowe-zdjecie.png','mimeType':'image/png','buffer':image('green')})
            page.wait_for_function("async pid=>(await(await fetch('/api/project/'+pid)).json()).project.assets.length===3",arg=pid)
            page.wait_for_function("async pid=>{const p=(await(await fetch('/api/project/'+pid)).json()).project;return p.elements[0].assetId===p.assets[2].id;}",arg=pid)
            page.click('[data-edit="add-track"]');page.fill('#newTrackName','B-roll');page.select_option('#newTrackKind','image');page.click('[data-edit="create-track"]');page.locator('#modal').wait_for(state='hidden')
            track=store.read(pid)['project']['tracks'][-1]['id'];lane=page.locator(f'[data-lane="{track}"]');lane.scroll_into_view_if_needed()
            page.drag_and_drop(f'[data-asset="{a}"]',f'[data-lane="{track}"]')
            page.wait_for_function("async pid=>(await(await fetch('/api/project/'+pid)).json()).project.elements.length===2",arg=pid)
            assert store.read(pid)['project']['elements'][-1]['trackId']==track
            page.click('[data-tab="Production"]');page.click('[data-lesson="open"]')
            page.fill('[data-lesson-brief="coreIdea"]','Człowiek dopracowuje ten sam projekt.')
            page.fill('[data-lesson-brief="openingQuestion"]','Kto ma ostatnie słowo?');page.fill('#lessonDuration','14')
            page.click('[data-lesson="plan"]');page.locator('#lessonReplace').wait_for();page.check('#lessonReplace');page.click('[data-lesson="assemble"]');page.locator('#modal').wait_for(state='hidden')
            assert len(store.read(pid)['project']['scenes'])==7
            page.click('#storyboardTab');page.locator('[data-lesson-scene]').first.click()
            page.fill('[data-lesson-scene-field="narration"]','Ty masz ostatnie słowo.')
            page.click('[data-lesson-save-scene]');page.locator('#modal').wait_for(state='hidden')
            assert store.read(pid)['project']['scenes'][0]['lesson']['narration']=='Ty masz ostatnie słowo.'
            page.set_viewport_size({'width':320,'height':760});page.click('#timelineTab')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert not errors
            browser.close()
    finally:srv.shutdown();srv.server_close()
