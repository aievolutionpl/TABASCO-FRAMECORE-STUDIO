"""Original MotionDuo implementations of source, magnetic and group workflows."""
from copy import deepcopy
import pytest
from framecore.api import API
from framecore.model import EditorError
from framecore.store import Store
import io
import json
import shutil
import subprocess
import time
from PIL import Image


@pytest.fixture
def real_source(tmp_path):
    if not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg required')
    from framecore.media_import import import_asset
    source = tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=red:s=160x90:r=12:d=2',
                    '-f','lavfi','-i','color=c=blue:s=160x90:r=12:d=2',
                    '-f','lavfi','-i','aevalsrc=if(lt(t\\,2)\\,0\\,0.6*sin(2*PI*440*t)):s=8000:d=4',
                    '-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0[v]',
                    '-map','[v]','-map','2:a','-c:v','libx264','-threads','1','-pix_fmt','yuv420p','-c:a','aac',str(source)],check=True)
    store=Store(tmp_path/'projects');pid=store.create('Monitor źródła','16:9',4)['project']['id']
    raw=store._load(pid);raw['project']['canvas'].update(width=160,height=90,fps=12);store._save(raw)
    state=import_asset(store,pid,source.read_bytes(),'red-then-blue.mp4',expected_revision=0)
    return store,pid,state['project']['assets'][0]['id']


def await_analysis(engine,pid,aid):
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        report=engine.status(pid,aid)
        if report['status'] not in {'queued','running'}:return report
        time.sleep(.05)
    pytest.fail('Audio analysis timeout')

@pytest.fixture
def edit(tmp_path):
    store=Store(tmp_path/'projects');pid=store.create('Wspólny montaż','16:9',20)['project']['id'];api=API(store,None)
    def call(tool,**args):return api.call(tool,{'project_id':pid,'expected_revision':store.read(pid)['project']['revision'],**args})
    return store,pid,api,call


def test_group_edits_preserve_spacing_and_undo_atomically(edit):
    store,pid,api,call=edit
    call('add_text',text='A',start=1,duration=2)
    call('add_shape',start=2,duration=2)
    s=call('add_text',text='B',start=5,duration=2)
    before=deepcopy(s['project']['elements']);ids=[before[0]['id'],before[1]['id']]
    s=call('move_clips',element_ids=ids,delta=1.5)
    assert s['project']['elements']==[{**e,'start':e['start']+1.5} if e['id'] in ids else e for e in before]
    call('undo');assert store.read(pid)['project']['elements']==before
    call('set_track',track_id='shape',property='locked',value=True);snapshot=store.read(pid)
    for tool,args in [('move_clips',{'delta':1}),('delete_clips',{}),('duplicate_clips',{'delta':2}),('set_clip_properties',{'properties':{'x':22}})]:
        with pytest.raises(EditorError):call(tool,element_ids=ids,**args)
        assert store.read(pid)==snapshot
    call('set_track',track_id='shape',property='locked',value=False)
    s=call('duplicate_clips',element_ids=ids,delta=6)
    copies=s['project']['elements'][3:]
    assert len(copies)==2 and [e['start'] for e in copies]==[7,8]
    assert all(a['id']!=b['id'] and a['style']==b['style'] for a,b in zip(copies,before))


def test_group_typography_splits_and_track_local_delete(edit):
    store,pid,api,call=edit
    for start in [1,4,8]:call('add_text',text='Tytuł',start=start,duration=2)
    s=call('add_shape',start=9,duration=2);before=deepcopy(s['project']['elements']);ids=[before[0]['id'],before[1]['id']]
    s=call('set_clip_properties',element_ids=ids,properties={'style.fontFamily':'Manrope','style.fontSize':42,'style.color':'#00aabb'})
    assert all(e['style']['fontFamily']=='Manrope' and e['style']['fontSize']==42 for e in s['project']['elements'][:2])
    assert s['project']['elements'][2:]==before[2:]
    s=call('delete_clips',element_ids=ids,ripple=True)
    assert [e['start'] for e in s['project']['elements']]==[4,9]
    call('undo');snapshot=store.read(pid)['project']
    s=call('split_clips',element_ids=ids,time=2)
    # Only the first selected clip intersects the cut; the other stays intact.
    assert len(s['project']['elements'])==5
    assert s['project']['elements'][0]['duration']==1 and s['project']['elements'][1]==snapshot['elements'][1]
    assert s['project']['elements'][-1]['start']==2
    call('undo');assert store.read(pid)['project']['elements']==snapshot['elements']


def test_magnetic_head_and_tail_trim_keep_source_and_gap(edit):
    store,pid,api,call=edit
    asset={'id':'asset_video','kind':'video','file':'assets/test.mp4','mime':'video/mp4','duration':10,'hasAudio':True,'name':'Video'}
    store.execute(pid,'add_asset',{'asset':asset},0)
    s=call('add_video',assetId=asset['id'],start=2,duration=3,sourceStart=1.5)
    eid=s['project']['elements'][0]['id']
    call('set_keyframes',element_id=eid,keyframes=[{'property':'x','time':0,'value':0},{'property':'x','time':3,'value':300}])
    s=call('add_video',assetId=asset['id'],start=7,duration=2);before=deepcopy(s['project']['elements'])
    s=call('magnetic_trim',element_id=eid,edge='start',delta=1)
    a,b=s['project']['elements'];assert (a['start'],a['duration'],a['sourceStart'],b['start'])==(2,2,2.5,6)
    assert a['keyframes'][0]['value']==100 and a['keyframes'][-1]['time']==2
    call('undo');assert store.read(pid)['project']['elements']==before
    s=call('magnetic_trim',element_id=eid,edge='end',delta=1)
    a,b=s['project']['elements'];assert (a['start'],a['duration'],a['sourceStart'],b['start'])==(2,4,1.5,8)
    call('undo')
    call('move_clip',element_id=eid,start=0)
    s=call('magnetic_trim',element_id=eid,edge='start',delta=-.5)
    a,b=s['project']['elements'];assert (a['start'],a['duration'],a['sourceStart'],b['start'])==(0,3.5,1,7.5)
    frozen=store.read(pid)
    for edge,delta in [('start',-2),('end',20),('start',4),('other',1)]:
        with pytest.raises(EditorError):call('magnetic_trim',element_id=eid,edge=edge,delta=delta)
        assert store.read(pid)==frozen


def test_range_inserts_video_and_audio_as_one_edit(edit):
    store,pid,api,call=edit
    asset={'id':'asset_video','kind':'video','file':'assets/test.mp4','mime':'video/mp4','duration':10,'hasAudio':True,'name':'Video'}
    store.execute(pid,'add_asset',{'asset':asset},0)
    s=call('insert_media_range',asset_id=asset['id'],source_start=1.25,source_end=3.75,start=4,include_audio=True)
    assert len(s['project']['elements'])==2
    assert [e['type'] for e in s['project']['elements']]==['video','audio']
    assert all((e['sourceStart'],e['start'],e['duration'])==(1.25,4,2.5) for e in s['project']['elements'])
    call('undo');assert store.read(pid)['project']['elements']==[]
    call('set_track',track_id='audio',property='locked',value=True);frozen=store.read(pid)
    for args in [{'source_start':1,'source_end':3,'include_audio':True},{'source_start':-1}, {'source_start':4,'source_end':3}, {'source_end':11}]:
        with pytest.raises(EditorError):call('insert_media_range',asset_id=asset['id'],**args)
        assert store.read(pid)==frozen


def test_group_invalid_ids_and_bounds_leave_document_unchanged(edit):
    store,pid,api,call=edit
    s=call('add_text',text='A',start=1,duration=2);eid=s['project']['elements'][0]['id'];frozen=store.read(pid)
    for ids,delta in [([],1),([eid,eid],1),(['missing'],1),([eid],-2),([eid],20)]:
        with pytest.raises(EditorError):call('move_clips',element_ids=ids,delta=delta)
        assert store.read(pid)==frozen
    tools={t['name']:t for t in api.tools()}
    assert tools['get_audio_waveform']['annotations']['readOnlyHint']
    assert tools['set_selection']['inputSchema']['properties']['element_ids']['minItems']==0
    for name in ['move_clips','duplicate_clips','delete_clips','split_clips','set_clip_properties','magnetic_trim','insert_media_range']:
        assert 'expected_revision' in tools[name]['inputSchema']['required']


@pytest.mark.browser
def test_real_source_range_waveform_and_export(real_source):
    from framecore.render import RenderJobs, probe
    store,pid,aid=real_source;api=API(store,RenderJobs(store))
    before=store.read(pid)
    api.call('analyze_media',{'project_id':pid,'asset_id':aid})
    assert await_analysis(api.media,pid,aid)['status']=='ready'
    def peaks(start):return api.call('get_audio_waveform',{'project_id':pid,'asset_id':aid,'source_start':start,'duration':1,'points':50})['peaks']
    assert max(peaks(0))<.01
    assert .4<max(peaks(2.25))<.8
    assert store.read(pid)==before
    with pytest.raises(EditorError):api.media.audio_waveform(pid,aid,3.5,1)
    state=api.call('insert_media_range',{'project_id':pid,'expected_revision':1,'asset_id':aid,'source_start':2.25,'source_end':3.75,'include_audio':True,'start':0})
    before=deepcopy(state);job=api.jobs.start(pid,state['project']['revision'],'draft')
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        job=api.jobs.get(job['id'])
        if job['status'] in {'complete','failed'}:break
        time.sleep(.1)
    assert job['status']=='complete',job
    out=store.directory(pid)/'exports'/job['id']/'framecore.mp4'
    info=probe(out);assert {s['codec_name'] for s in info['streams']}=={'h264','aac'}
    assert abs(float(info['format']['duration'])-4)<.1
    pixels=subprocess.check_output(['ffmpeg','-v','error','-ss','0.3','-i',str(out),'-frames:v','1','-f','image2pipe','-vcodec','png','-threads','1','-'])
    r,g,b=Image.open(io.BytesIO(pixels)).convert('RGB').getpixel((80,45))
    assert b>180 and r<40 and g<40,(r,g,b)
    pcm=subprocess.check_output(['ffmpeg','-v','error','-ss','0.25','-i',str(out),'-t','0.5','-vn','-ac','1','-ar','8000','-f','s16le','-'])
    from framecore.media import waveform
    assert max(waveform(pcm)['peaks'])>.4
    assert store.read(pid)==before


@pytest.mark.browser
def test_source_monitor_group_drag_magnetic_trim_and_volume(real_source,tmp_path):
    from playwright.sync_api import sync_playwright
    from framecore.server import start_background
    store,pid,aid=real_source;server,_=start_background(store);errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'))
            page=browser.new_page(viewport={'width':1512,'height':982})
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.add_init_script(f'localStorage.setItem("framecore-project",{json.dumps(pid)});localStorage.setItem("framecore-onboarding-v2","done")')
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.wait_for_function('document.querySelector("#player").ready')
            page.click('[data-tab="Media"]')
            page.click(f'[data-source-asset="{aid}"]')
            page.locator('#sourceIn').fill('2.25');page.locator('#sourceOut').fill('3.75')
            page.click('[data-source-insert]')
            page.wait_for_function('document.querySelectorAll(".clip").length===2')
            page.get_by_text('2 zaznaczone klipy',exact=True).wait_for()
            page.wait_for_function('document.querySelector("[data-waveform]").dataset.waveformState==="ready"',timeout=20000)
            state=store.read(pid);video,audio=state['project']['elements']
            assert state['project']['revision']==2
            assert all(e['sourceStart']==2.25 and e['duration']==1.5 for e in [video,audio])
            canvas=page.locator('[data-waveform]')
            assert canvas.evaluate('el=>{const d=el.getContext("2d").getImageData(0,0,el.width,el.height).data;return d.filter((v,i)=>i%4===3&&v>0).length>el.width*6}')
            page.locator('#groupDelta').fill('.5');page.click('[data-edit="move-group"]')
            page.wait_for_function('document.querySelector("[data-clip]").style.left==="12.5%"')
            assert all(e['start']==.5 for e in store.read(pid)['project']['elements'])
            page.click('#undo');page.wait_for_function('document.querySelector("[data-clip]").style.left==="0%"')
            # Drag a selected clip: both tracks move together, in one history step.
            page.uncheck('#snap')
            box=page.locator(f'[data-clip="{video["id"]}"]').bounding_box()
            lane=page.locator(f'[data-clip="{video["id"]}"]').locator('..').bounding_box()
            page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
            page.mouse.down();page.mouse.move(box['x']+box['width']/2+lane['width']/8,box['y']+box['height']/2,steps=8);page.mouse.up()
            page.wait_for_function('document.querySelector("[data-clip]").style.left==="12.5%"')
            assert all(e['start']==.5 for e in store.read(pid)['project']['elements'])
            page.click('#undo');page.wait_for_function('document.querySelector("[data-clip]").style.left==="0%"')
            # A volume-line gesture affects only audio and remains reversible.
            page.locator(f'[data-clip="{audio["id"]}"]').click(position={'x':25,'y':10})
            line=page.locator('[data-volume]').bounding_box();clip=page.locator(f'[data-clip="{audio["id"]}"]').bounding_box()
            page.mouse.move(line['x']+line['width']/2,line['y']+line['height']/2);page.mouse.down()
            page.mouse.move(line['x']+line['width']/2,clip['y']+clip['height']*.7,steps=8);page.mouse.up()
            page.wait_for_function('!document.querySelector("[data-volume]").title.includes("100%")')
            assert store.read(pid)['project']['elements'][1]['audio']['gain']<1
            page.click('#undo');page.wait_for_function('document.querySelector("[data-volume]").title.includes("100%")')
            # Magnetic head trim anchors the clip and advances the source.
            page.check('#magnetic');page.locator(f'[data-clip="{video["id"]}"]').click(position={'x':25,'y':10})
            handle=page.locator(f'[data-clip="{video["id"]}"] .trim-handle:not(.right)').bounding_box()
            page.mouse.move(handle['x']+2,handle['y']+handle['height']/2);page.mouse.down()
            page.mouse.move(handle['x']+2+lane['width']/8,handle['y']+handle['height']/2,steps=8);page.mouse.up()
            page.wait_for_function('document.querySelector("[data-property=duration]").value==="1"')
            v,a=store.read(pid)['project']['elements'];assert (v['start'],v['duration'],v['sourceStart'])==(0,1,2.75)
            assert (a['start'],a['duration'],a['sourceStart'])==(0,1.5,2.25)
            # Additive selection works with a real modifier click.
            page.locator(f'[data-clip="{audio["id"]}"]').click(modifiers=['Control'],position={'x':25,'y':10})
            page.get_by_text('2 zaznaczone klipy',exact=True).wait_for()
            page.screenshot(path=str(tmp_path/'concat-editor.png'))
            for w,h in [(320,760),(390,844),(900,900)]:
                page.set_viewport_size({'width':w,'height':h})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert errors==[]
            browser.close()
    finally:server.shutdown();server.server_close()
