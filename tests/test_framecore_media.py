"""Real media derivatives, cache safety, API discovery and UI compatibility."""
import io
import json
import shutil
import subprocess
import time
import wave
from pathlib import Path

import pytest
from PIL import Image

from framecore.api import API
from framecore.media import MediaEngine, waveform
from framecore.media_import import import_asset
from framecore.model import EditorError
from framecore.render import RenderJobs
from framecore.store import Store


def setup_asset(tmp_path, filename='picture.png', data=None):
    store=Store(tmp_path/'projects')
    state=store.create('Media regression')
    if data is None:
        out=io.BytesIO();Image.new('RGB',(800,400),'orange').save(out,format='PNG');data=out.getvalue()
    state=import_asset(store,state['project']['id'],data,filename,expected_revision=0)
    return store,state['project']['id'],state['project']['assets'][0]['id']


def finished(engine,pid,aid):
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        report=engine.status(pid,aid)
        if report['status'] not in {'queued','running'}:return report
        time.sleep(.05)
    pytest.fail('Media analysis did not finish')


def test_image_cache_revision_and_legacy_imports(tmp_path):
    from framecore.persistence import file_lock, atomic_write
    from vstudio.locking import file_lock as legacy_lock, atomic_write as legacy_write
    from framecore.server import import_asset as legacy_import
    assert legacy_lock is file_lock and legacy_write is atomic_write and legacy_import is import_asset
    store,pid,aid=setup_asset(tmp_path)
    before=store.read(pid)
    api=API(store,RenderJobs(store));engine=api.media
    assert api.call('get_media_analysis',{'project_id':pid,'asset_id':aid})['status']=='not_started'
    api.call('analyze_media',{'project_id':pid,'asset_id':aid})
    report=finished(engine,pid,aid)
    assert report['status']=='ready',report
    assert report['metadata']['width']==800
    path=engine.artifact(pid,aid,'thumbnail.jpg')
    with Image.open(path) as picture: assert picture.size==(640,320)
    saved=path.stat().st_mtime_ns
    assert engine.start(pid,aid)['status']=='ready'
    assert path.stat().st_mtime_ns==saved
    assert store.read(pid)==before
    with pytest.raises(EditorError):engine.artifact(pid,aid,'../../state.json')
    with pytest.raises(EditorError):engine.status(pid,'missing')
    for name in ('analyze_media','get_media_analysis'):
        tool=next(t for t in api.tools() if t['name']==name)
        assert 'asset_id' in tool['inputSchema']['required']
    path.write_bytes(b'corrupt thumbnail')
    assert engine.status(pid,aid)['status']=='failed'
    engine.start(pid,aid)
    assert finished(engine,pid,aid)['status']=='ready'
    source=store.directory(pid)/before['project']['assets'][0]['file']
    Image.new('RGB',(200,100),'blue').save(source)
    assert engine.status(pid,aid)['status']=='not_started'


def test_waveform_and_silence():
    result=waveform(b'\0\0'*8000)
    assert result['duration']==1
    assert len(result['peaks'])<=1200 and max(result['peaks'])==0
    assert result['silence']==[{'start':0,'end':1}]
    assert waveform(b'')['peaks']==[]


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg required')
@pytest.mark.parametrize('kind',['audio','video'])
def test_real_media_derivatives(tmp_path,kind):
    if kind=='audio':
        data=io.BytesIO()
        with wave.open(data,'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(8000);out.writeframes(b'\0\0'*8000)
        content=data.getvalue();name='silence.wav'
    else:
        source=tmp_path/'source.mp4'
        subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=12','-f','lavfi','-i','sine=frequency=220','-t','1','-c:v','libx264','-threads','1','-c:a','aac',str(source)],check=True)
        content=source.read_bytes();name='source.mp4'
    store,pid,aid=setup_asset(tmp_path,name,content)
    engine=MediaEngine(store);engine.start(pid,aid);report=finished(engine,pid,aid)
    assert report['status']=='ready',report
    assert report['metadata']['kind']==kind
    wave_data=json.loads(engine.artifact(pid,aid,'waveform.json').read_text())
    assert .9<=wave_data['duration']<=1.2
    if kind=='video':
        with Image.open(engine.artifact(pid,aid,'contact-sheet.jpg')) as sheet:assert sheet.size==(960,360)
        info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(engine.artifact(pid,aid,'proxy.mp4'))]))
        assert any(s['codec_type']=='video' and s['codec_name']=='h264' for s in info['streams'])
        assert len(report['contact_sheet_times'])==6


def test_worker_failure_is_reported_without_project_changes(tmp_path,monkeypatch):
    store,pid,aid=setup_asset(tmp_path)
    before=store.read(pid)
    def broken(*args,**kwargs):raise OSError('decoder unavailable')
    monkeypatch.setattr('framecore.media.Image.open',broken)
    engine=MediaEngine(store);engine.start(pid,aid)
    report=finished(engine,pid,aid)
    assert report['status']=='failed' and 'decoder unavailable' in report['error']
    assert store.read(pid)==before


@pytest.mark.browser
def test_media_panel_analyzes_existing_project(tmp_path):
    from playwright.sync_api import sync_playwright
    from framecore.server import start_background
    store,pid,aid=setup_asset(tmp_path)
    before=store.read(pid)['project']['revision']
    server,_=start_background(store)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch()
            page=browser.new_page(viewport={'width':1400,'height':1000})
            page.add_init_script(f'localStorage.setItem("framecore-project",{json.dumps(pid)});localStorage.setItem("framecore-onboarding-v2","done")')
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.click('[data-media-analysis]')
            page.locator('#mediaAnalysisResult').get_by_text('Nie analizowano',exact=True).wait_for()
            page.click('#startMediaAnalysis')
            page.locator('#mediaAnalysisResult').get_by_text('Gotowe',exact=True).wait_for(timeout=15000)
            image=page.locator('#mediaAnalysisResult img')
            page.wait_for_function('document.querySelector("#mediaAnalysisResult img")?.naturalWidth===640')
            assert store.read(pid)['project']['revision']==before
            browser.close()
    finally:
        server.shutdown();server.server_close()
