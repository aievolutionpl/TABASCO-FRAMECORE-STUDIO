"""Real decoded media, frozen revision identity and browser integration."""
import json
import shutil
import subprocess
from zipfile import ZipFile
import pytest
from playwright.sync_api import sync_playwright
from framecore.api import API
from framecore.model import EditorError, uid
from framecore.quality import measure
from framecore.render import RenderJobs
from framecore.server import start_background
from framecore.store import Store


def film(path, visual='color=c=black:s=320x180:r=20:d=4', sound=None):
    cmd=['ffmpeg','-y','-v','error','-f','lavfi','-i',visual]
    if sound:cmd+=['-f','lavfi','-i',sound]
    subprocess.run(cmd+['-t','4','-c:v','libx264','-pix_fmt','yuv420p']+(['-c:a','aac'] if sound else [])+[str(path)],check=True,capture_output=True)


def completed(tmp_path):
    store=Store(tmp_path/'projects');p=store.create('Pomiar','16:9',4)['project'];pid=p['id']
    jobs=RenderJobs(store);jid=uid('render');out=store.directory(pid)/'exports'/jid;out.mkdir(parents=True)
    film(out/'framecore.mp4')
    from framecore.delivery import freeze_notices
    freeze_notices(p,out)
    (out/'project.json').write_text(json.dumps(p))
    (jobs.directory/(jid+'.json')).write_text(json.dumps({'id':jid,'project_id':pid,'revision':0,'status':'complete'}))
    return store,API(store,jobs),pid,jid,out


def test_real_static_motion_silence_and_loudness(tmp_path):
    static=tmp_path/'static.mp4';film(static)
    r=measure(static,'mute')
    assert r['motion']['frozenSeconds']>3.5
    assert r['motion']['longestHold']>3.5
    assert {'frozen_total','long_hold'} <= {w['code'] for w in r['warnings']}
    assert not r['audio']['present'] and 'audio_missing' not in {w['code'] for w in r['warnings']}
    moving=tmp_path/'moving.mp4';film(moving,'testsrc2=s=320x180:r=20:d=4','sine=frequency=440:duration=4')
    moving_report=measure(moving,'punchy')
    assert moving_report['motion']['frozenSeconds']<.5
    assert moving_report['audio']['present']
    assert -30 < moving_report['audio']['integratedLufs'] < -10
    assert moving_report['audio']['truePeakDbfs'] < -1
    assert moving_report['audio']['rangeLu'] is not None
    assert 'loudness' in {w['code'] for w in moving_report['warnings']}
    silent=tmp_path/'silent.mp4';film(silent,sound='anullsrc=r=48000:cl=stereo')
    silence=measure(silent)
    assert 'loudness' in {w['code'] for w in silence['warnings']}
    json.dumps(silence,allow_nan=False)
    with pytest.raises(EditorError):measure(static,['calm'])


def test_frozen_export_report_delivery_and_changed_bytes(tmp_path):
    store,api,pid,jid,out=completed(tmp_path)
    with pytest.raises(EditorError,match='Najpierw'):api.call('get_quality_report',{'project_id':pid,'job_id':jid})
    r=api.call('analyze_export',{'project_id':pid,'job_id':jid,'profile':'mute'})
    assert r['revision']==0 and len(r['sha256'])==64
    api.call('rename_project',{'project_id':pid,'expected_revision':0,'name':'Nowy montaż'})
    assert api.call('get_quality_report',{'project_id':pid,'job_id':jid})==r
    assert store.read(pid)['project']['revision']==1
    bundle=api.call('package_delivery',{'project_id':pid,'job_id':jid})
    with ZipFile(out/'delivery.zip') as z:assert json.loads(z.read('quality-report.json'))==r
    other=store.create('Inny film')['project']['id']
    with pytest.raises(EditorError):api.call('analyze_export',{'project_id':other,'job_id':jid})
    with pytest.raises(EditorError):api.call('analyze_export',{'project_id':pid,'job_id':'../../escape'})
    assert api.call('get_motion_playbook')['review']['criticPrompt']
    tools={t['name']:t for t in api.tools()}
    assert 'job_id' in tools['analyze_export']['inputSchema']['required']
    assert tools['get_quality_report']['annotations']['readOnlyHint']
    (out/'framecore.mp4').write_bytes(b'changed')
    with pytest.raises(EditorError,match='zmienił'):api.call('get_quality_report',{'project_id':pid,'job_id':jid})


@pytest.mark.browser
def test_export_measurement_button_download_and_mobile(tmp_path):
    store=Store(tmp_path/'projects');p=store.create('Film bez dźwięku','16:9',1)['project'];pid=p['id']
    raw=store._load(pid);raw['project']['canvas'].update(width=240,height=136);store._save(raw)
    store.execute(pid,'add_text',{'text':'Film','x':30,'y':20,'width':180,'height':70,'duration':1,'style':{'fontSize':32}},0)
    srv,_=start_background(store);base=f'http://127.0.0.1:{srv.server_port}';errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(**({'executable_path':shutil.which('chromium')} if shutil.which('chromium') else {}))
            page=browser.new_page(viewport={'width':1512,'height':982});page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base);page.wait_for_function('document.querySelector("#player").ready')
            page.click('#export');page.click('#startExport')
            page.locator('[data-measure-job]').wait_for(timeout=60000)
            page.select_option('#measureProfile','mute');page.click('[data-measure-job]')
            page.locator('#qualityReport a').wait_for(timeout=30000)
            assert 'Brak ścieżki audio' in page.locator('#qualityReport').inner_text()
            report=page.request.get(base+page.locator('#qualityReport a').get_attribute('href'))
            assert report.ok and report.json()['profile']=='mute'
            page.set_viewport_size({'width':390,'height':844})
            assert page.locator('#qualityReport').is_visible()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(tmp_path/'export-quality-mobile.png'))
            page.click('[data-delivery-job]');page.locator('a[download]').filter(has_text='ZIP').wait_for()
            assert not errors
            browser.close()
    finally:srv.shutdown();srv.server_close()


@pytest.mark.browser
def test_review_detects_seek_history_drift(tmp_path,monkeypatch):
    from framecore import composition
    from framecore.production import CHECKLIST
    store=Store(tmp_path/'projects');p=store.create('Historia przewijania','16:9',2)['project'];pid=p['id']
    raw=store._load(pid);raw['project']['canvas'].update(width=240,height=136);store._save(raw)
    store.execute(pid,'add_text',{'text':'Stan','x':20,'y':20,'width':190,'height':80,'duration':2,'style':{'fontSize':32}},0)
    compile_project=composition.compile_project
    def drift(*args,**kwargs):
        html=compile_project(*args,**kwargs)
        return html.replace('</body>', '''<script>const originalSeek=window.seek;let visits=0;
window.seek=async(t)=>{await originalSeek(t);document.querySelector('[data-element-id]').style.color='rgb('+((++visits*37)%255)+',0,0)'};</script></body>''')
    monkeypatch.setattr(composition,'compile_project',drift)
    api=API(store,RenderJobs(store));args={'project_id':pid,'expected_revision':1}
    r=api.call('create_review',{**args,'times':[.5,1.5]})
    assert any(e['code']=='seek_inconsistent' for e in r['errors'])
    assert not all(t['identicalPixels'] for t in r['determinism'])
    with pytest.raises(EditorError,match='Napraw'):
        api.call('review_verdict',{**args,'review_id':r['id'],'verdict':'approved','checklist':dict.fromkeys(CHECKLIST,True)})
