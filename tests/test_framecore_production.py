"""Production evidence, revision gates and independent format compositions."""
import json
import shutil
import time
from zipfile import ZipFile
import pytest
from playwright.sync_api import sync_playwright
from framecore.api import API
from framecore.model import EditorError
from framecore.production import CHECKLIST, status
from framecore.render import RenderJobs
from framecore.server import start_background
from framecore.store import Store


def setup_project(tmp_path):
    store=Store(tmp_path/'projects');s=store.create('Film produkcyjny','16:9',2);pid=s['project']['id']
    raw=store._load(pid);raw['project']['canvas'].update(width=960,height=540);store._save(raw)
    s=store.execute(pid,'add_text',{'text':'Prawdziwa historia','x':80,'y':80,'width':730,'height':140,'duration':2,'style':{'fontFamily':'Manrope','fontSize':52}},0)
    api=API(store,RenderJobs(store))
    return store,api,pid


def edit(api,pid,name,args=None):
    return api.call(name,{'project_id':pid,'expected_revision':api.store.read(pid)['project']['revision'],**(args or {})})


def test_contract_gates_assets_atomic_validation_and_undo(tmp_path):
    store,api,pid=setup_project(tmp_path)
    c={'product':'FrameCore','message':'Prawdziwe materiały i kontrola jakości','requireReview':True,
       'requiredAssets':[{'label':'Rzeczywiste logo','assetId':None}]}
    edit(api,pid,'set_production_contract',{'contract':c})
    with pytest.raises(EditorError,match='Brak wymaganego'):
        edit(api,pid,'export',{'quality':'draft'})
    before=store.read(pid)
    with pytest.raises(EditorError):edit(api,pid,'set_production_contract',{'contract':{'requireReview':'yes'}})
    assert store.read(pid)==before
    edit(api,pid,'undo');assert 'production' not in store.read(pid)['project']
    edit(api,pid,'set_production_contract',{'contract':{**c,'requiredAssets':[]}})
    with pytest.raises(EditorError,match='beat'):edit(api,pid,'export')
    edit(api,pid,'annotate_story_beats')
    beat=store.read(pid)['project']['scenes'][0]['beat']
    assert beat['focusElementId']==store.read(pid)['project']['elements'][0]['id']
    with pytest.raises(EditorError,match='zatwierdź'):edit(api,pid,'export')
    focus=beat['focusElementId'];edit(api,pid,'delete_clip',{'element_id':focus})
    assert store.read(pid)['project']['scenes'][0]['beat']['focusElementId'] is None
    edit(api,pid,'undo');assert store.read(pid)['project']['scenes'][0]['beat']['focusElementId']==focus


def test_variants_preserve_source_and_require_independent_review(tmp_path):
    store,api,pid=setup_project(tmp_path)
    edit(api,pid,'add_library_asset',{'asset_id':'fluent-rocket','duration':2})
    edit(api,pid,'annotate_story_beats');source=store.read(pid)
    variants=[edit(api,pid,'create_format_variant',{'format':f}) for f in ['9:16','4:5','16:9']]
    assert store.read(pid)==source
    for v in variants:
        p=v['project'];assert p['id']!=pid and p['production']['requireReview']
        assert p['metadata']['variantOf']['revision']==source['project']['revision']
        assert (store.directory(p['id'])/p['assets'][0]['file']).read_bytes()==(store.directory(pid)/p['assets'][0]['file']).read_bytes()
        assert not status(p,store.directory(p['id']))['reviewApproved']
    vertical=variants[0]['project']['elements'];wide=variants[2]['project']['elements']
    assert vertical[1]['y']>vertical[0]['y']+vertical[0]['height']
    assert wide[1]['x']>wide[0]['x']+wide[0]['width']
    count=len(store.list())
    with pytest.raises(EditorError):edit(api,pid,'create_format_variant',{'format':'10:3'})
    assert len(store.list())==count


def test_motion_rules_preserve_locked_tracks_and_history(tmp_path):
    store,api,pid=setup_project(tmp_path)
    edit(api,pid,'add_library_asset',{'asset_id':'fluent-rocket','duration':2})
    edit(api,pid,'apply_motion_rules');p=store.read(pid)['project']
    assert p['elements'][1]['motion']['duration']>p['elements'][0]['motion']['duration']
    assert p['elements'][1]['motion']['easing']=='quint-out'
    edit(api,pid,'set_track',{'track_id':'text','property':'locked','value':True});before=store.read(pid)
    with pytest.raises(EditorError):edit(api,pid,'apply_motion_rules')
    assert store.read(pid)==before


@pytest.mark.browser
def test_review_measures_real_overflow_and_rejects_stale_evidence(tmp_path):
    store,api,pid=setup_project(tmp_path)
    edit(api,pid,'set_production_contract',{'contract':{'product':'Studio','message':'Jedna historia','requireReview':True}})
    edit(api,pid,'annotate_story_beats')
    edit(api,pid,'add_library_asset',{'asset_id':'fluent-rocket','duration':2})
    eid=store.read(pid)['project']['elements'][0]['id']
    edit(api,pid,'resize_element',{'element_id':eid,'width':50,'height':15})
    broken=edit(api,pid,'create_review',{'times':[1]})
    assert any(e['code']=='text_overflow' for e in broken['errors'])
    with pytest.raises(EditorError):edit(api,pid,'review_verdict',{'review_id':broken['id'],'verdict':'approved','checklist':dict.fromkeys(CHECKLIST,True)})
    edit(api,pid,'resize_element',{'element_id':eid,'width':730,'height':140})
    with pytest.raises(EditorError):edit(api,pid,'review_verdict',{'review_id':broken['id'],'verdict':'approved','checklist':dict.fromkeys(CHECKLIST,True)})
    good=edit(api,pid,'create_review',{'times':[1]});assert not good['errors']
    edit(api,pid,'review_verdict',{'review_id':good['id'],'verdict':'approved','checklist':dict.fromkeys(CHECKLIST,True),'notes':'Klatka obejrzana, film bez audio.'})
    assert status(store.read(pid)['project'],store.directory(pid))['finalReady']
    from framecore.mcp import FrameCoreMCP
    mcp=FrameCoreMCP(api);mcp.initialized=True
    result=mcp._dispatch('tools/call',{'name':'get_review','arguments':{'project_id':pid,'review_id':good['id']}})
    assert not result['isError'] and result['content'][1]['mimeType']=='image/jpeg'
    asset=store.read(pid)['project']['assets'][0];path=store.directory(pid)/asset['file'];original=path.read_bytes()
    path.write_bytes(original+b'changed')
    assert not status(store.read(pid)['project'],store.directory(pid))['reviewApproved']
    assert not api.call('get_review',{'project_id':pid,'review_id':good['id']})['current']
    with pytest.raises(EditorError):edit(api,pid,'export')
    path.write_bytes(original)
    edit(api,pid,'set_property',{'element_id':eid,'property':'text','value':'Nowy komunikat'})
    assert not status(store.read(pid)['project'],store.directory(pid))['reviewApproved']
    with pytest.raises(EditorError):edit(api,pid,'export')


@pytest.mark.browser
def test_production_ui_review_export_and_delivery(tmp_path):
    store,api,pid=setup_project(tmp_path);srv,_=start_background(store);base=f'http://127.0.0.1:{srv.server_port}';errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'));page=browser.new_page(viewport={'width':1512,'height':982})
            page.add_init_script("localStorage.setItem('framecore-onboarding-v2', 'done')")
            page.on('pageerror',lambda e:errors.append(str(e)));page.goto(base)
            page.wait_for_function('document.querySelector("#player").ready');page.click('[data-tab="Production"]')
            page.fill('[data-production-field="product"]','FrameCore')
            page.fill('[data-production-field="message"]','Jedna historia. Rzeczywiste klatki.')
            page.check('#requireProductionReview');page.click('[data-production-action="save"]')
            page.click('[data-production-action="beats"]')
            page.wait_for_selector('[data-production-scene]');page.click('[data-production-scene]')
            page.fill('[data-production-field="purpose"]','Pokazać prawdziwy nagłówek');page.click('[data-production-save-beat]')
            page.click('[data-production-action="review"]');page.wait_for_selector('.review-sheet',timeout=45000)
            assert page.locator('.review-sheet').evaluate('el=>el.complete&&el.naturalWidth>0')
            for check in CHECKLIST:page.check(f'[data-review-check="{check}"]')
            page.fill('#reviewNotes','Przegląd klatek wykonany; świadomie bez dźwięku.')
            page.click('[data-production-action="approve"]')
            page.wait_for_function('!document.querySelector("#modal").open')
            assert status(store.read(pid)['project'],store.directory(pid))['reviewApproved']
            page.click('#export');page.click('#startExport')
            page.wait_for_selector('a[href$="framecore.mp4"]',timeout=180000)
            page.click('[data-delivery-job]');page.wait_for_selector('a[href$="delivery.zip"]')
            url=page.locator('a[href$="delivery.zip"]').get_attribute('href')
            response=page.request.get(base+url);assert response.status==200
            from io import BytesIO
            with ZipFile(BytesIO(response.body())) as archive:
                assert {'framecore.mp4','brief.json','shot-list.json','assets-manifest.json','motion-rules.json','project.json','CREDITS.md','review/review.json','review/contact-sheet.jpg','licenses/manrope-OFL.txt','licenses/FRAMECORE-MIT.txt','font-manifest.json'}<=set(archive.namelist())
                reviewed=json.loads(archive.read('review/review.json'));assert reviewed['verdict']=='approved'
                assert json.loads(archive.read('project.json'))['revision']==reviewed['revision']
            assert errors==[]
            browser.close()
    finally:srv.shutdown();srv.server_close()


def test_production_example_is_independent_and_needs_fresh_review(tmp_path):
    from framecore.sample import create_creator_pack
    store=Store(tmp_path/'projects')
    first=create_creator_pack(store,'production-pipeline');second=create_creator_pack(store,'production-pipeline')
    assert first['project']['id']!=second['project']['id']
    assert first['project']['revision']==0 and first['project']['production']['requireReview']
    assert store.read(first['project']['id'])['project']==first['project']
    assert not status(first['project'],store.directory(first['project']['id']))['reviewApproved']
    assert not status(first['project'],store.directory(first['project']['id']))['blockers']


@pytest.mark.browser
def test_export_audio_uses_frozen_copy_if_live_asset_changes(tmp_path,monkeypatch):
    import subprocess
    from framecore.server import import_asset
    from framecore.sample import soundtrack
    store,api,pid=setup_project(tmp_path)
    source=soundtrack(2)
    s=import_asset(store,pid,source,'soundtrack.wav','audio',store.read(pid)['project']['revision'])
    asset=s['project']['assets'][0];edit(api,pid,'add_audio',{'assetId':asset['id'],'duration':2})
    raw=store._load(pid);raw['project']['canvas'].update(width=240,height=136);store._save(raw)
    live=store.directory(pid)/asset['file'];original_run=subprocess.run
    def change_after_picture(cmd,*args,**kwargs):
        result=original_run(cmd,*args,**kwargs)
        if len(cmd)>1 and str(cmd[1]).endswith('html_to_video.py'):
            # Keep the valid WAV header, replace source samples while rendering.
            live.write_bytes(source[:44]+bytes(len(source)-44))
        return result
    monkeypatch.setattr(subprocess,'run',change_after_picture)
    job=edit(api,pid,'export');deadline=time.time()+90
    while job['status'] not in {'failed','complete'} and time.time()<deadline:
        time.sleep(.1);job=api.jobs.get(job['id'])
    assert job['status']=='complete',job
    output=store.directory(pid)/'exports'/job['id']
    assert (output/asset['file']).read_bytes()==source
    decoded=original_run(['ffmpeg','-v','error','-i',str(output/'framecore.mp4'),'-vn','-f','s16le','-ac','1','pipe:1'],capture_output=True,check=True).stdout
    import struct
    samples=struct.unpack('<'+'h'*(len(decoded)//2),decoded)
    assert max(abs(v) for v in samples)>500  # original soundtrack survived, not silence
