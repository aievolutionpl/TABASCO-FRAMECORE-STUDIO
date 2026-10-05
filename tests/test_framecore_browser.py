"""Acceptance slice: upload -> storyboard -> live MCP -> undo -> actual MP4."""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import pytest
from PIL import Image
from playwright.sync_api import sync_playwright

from framecore.server import start_background
from framecore.store import Store
from vstudio.renderers.html_to_video import launch_browser

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.browser
def test_editable_reel_human_external_agent_undo_export(tmp_path):
    store = Store(tmp_path / "projects")
    srv, _ = start_background(store)
    base = f"http://127.0.0.1:{srv.server_port}"
    product, logo, video = [tmp_path / name for name in ("product.png", "logo.png", "footage.mp4")]
    Image.new('RGB', (400, 600), '#607647').save(product)
    Image.new('RGB', (120, 40), '#c1df98').save(logo)
    subprocess.run(['ffmpeg','-y','-f','lavfi','-i','testsrc2=size=180x320:rate=30','-f','lavfi','-i','sine=frequency=220:sample_rate=44100',
                    '-t','3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(video)],check=True,capture_output=True)
    errors=[]
    try:
        with sync_playwright() as pw:
            browser=launch_browser(pw, None)
            page=browser.new_page(viewport={'width':1512,'height':982})
            page.add_init_script("localStorage.setItem('framecore-onboarding-v2', 'done')")
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base)
            page.wait_for_function('document.querySelector("#player").ready')
            page.click('#newProject')
            page.fill('#newName','Acceptance product reel')
            page.click('#createProject')
            page.wait_for_function('document.querySelector("#projectMenu").textContent.includes("Acceptance product reel")')
            page.set_input_files('#fileInput',[str(product),str(logo),str(video)])
            page.wait_for_function('document.querySelectorAll(".asset-card").length === 3')
            page.click('[data-tab="Templates"]')
            page.click('[data-plan]')
            page.wait_for_selector('.plan-item')
            assert page.locator('.plan-item').count()==6
            page.click('#assemble')
            page.wait_for_function('document.querySelectorAll(".clip.text").length===6')
            page.wait_for_function('document.querySelector("#player").ready')
            page.locator('.clip.text').nth(1).click()
            page.fill('[data-property="text"]','Human edited headline')
            page.locator('[data-property="text"]').press('Tab')
            page.wait_for_function('document.querySelectorAll(".clip.text")[1].textContent.includes("Human edited headline")')
            page.click('#agentTab')
            pid=page.evaluate('localStorage.getItem("framecore-project")')
            proc=subprocess.Popen([sys.executable,str(REPO/'framecore.py'),'mcp','--root',str(store.root)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,cwd=REPO)
            def rpc(mid,method,params):
                proc.stdin.write(json.dumps({'jsonrpc':'2.0','id':mid,'method':method,'params':params})+'\n');proc.stdin.flush()
                return json.loads(proc.stdout.readline())['result']
            def tool(mid,name,args):
                result=rpc(mid,'tools/call',{'name':name,'arguments':{'project_id':pid,**args}})
                assert not result['isError'],result
                return json.loads(result['content'][0]['text'])
            try:
                rpc(1,'initialize',{'protocolVersion':'2025-06-18'})
                ctx=tool(2,'get_selection',{})
                assert ctx['selected'][0]['text']=='Human edited headline'
                eid=ctx['selection'][0];start=ctx['selected'][0]['start']
                proposal=tool(3,'propose_changes',{'expected_revision':ctx['revision'],'description':'Earlier, stronger headline',
                    'commands':[{'name':'move_clip','args':{'element_id':eid,'start':start-.4}},
                                {'name':'apply_motion','args':{'element_id':eid,'motion_id':'impact-rise','duration':.5}}]})
                page.wait_for_selector('[data-apply]',timeout=10000)
                tool(4,'apply_proposal',{'expected_revision':ctx['revision'],'proposal_id':proposal['proposals'][-1]['id']})
                page.wait_for_function('(id)=>document.querySelector(`[data-clip="${id}"]`).title.includes("1.60s")',arg=eid)
            finally:
                proc.stdin.close();proc.wait(timeout=10)
            page.click('#undo')
            page.wait_for_function('(id)=>document.querySelector(`[data-clip="${id}"]`).title.includes("2.00s")',arg=eid)
            page.click('#propertiesTab')
            page.fill('[data-property="x"]','140')
            page.locator('[data-property="x"]').press('Tab')
            page.wait_for_function('document.querySelector("[data-property=x]").value==="140"')
            # UI export freezes the same model used by the live agent.
            page.click('#export')
            with page.expect_response(lambda response: response.url.endswith('/api/export')) as started:
                page.click('#startExport')
            job=started.value.json()
            assert started.value.ok,job
            deadline=time.monotonic()+600
            while time.monotonic()<deadline:
                job=srv.jobs.get(job['id'])
                assert job['status']!='failed',job.get('error')
                if job['status']=='complete':break
                page.wait_for_timeout(500)
            assert job['status']=='complete',f'Render deadline exceeded: {job}'
            page.wait_for_selector('a[href$="framecore.mp4"]',timeout=10000)
            download=page.locator('a[href$="framecore.mp4"]').get_attribute('href')
            with urlopen(base+download) as response:
                assert response.status==200
                assert len(response.read())>10000
            output=store.directory(pid)/'exports'/download.split('/')[-2]/'framecore.mp4'
            info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)]))
            stream=next(s for s in info['streams'] if s['codec_type']=='video')
            assert (stream['width'],stream['height'])==(1080,1920)
            assert stream['codec_name']=='h264'
            assert abs(float(info['format']['duration'])-15)<.1
            assert any(s['codec_type']=='audio' for s in info['streams'])
            assert errors==[]
            page.click('[data-close]')
            page.screenshot(path=str(tmp_path/'framecore-acceptance.png'))
            browser.close()
    finally:
        srv.shutdown();srv.server_close()


@pytest.mark.browser
def test_polish_editor_new_tools_and_deterministic_motion(tmp_path):
    import base64
    import io
    from framecore.api import API
    from framecore.render import RenderJobs
    from framecore.composition import compile_project
    from framecore.motion import registry
    store=Store(tmp_path/'projects')
    s=store.create('Test ruchu',duration=6)
    pid=s['project']['id']
    s=store.execute(pid,'add_text',{'text':'Wspólny film','duration':4,'x':100},0)
    eid=s['project']['elements'][0]['id']
    s=store.execute(pid,'set_keyframes',{'element_id':eid,'keyframes':[{'property':'x','time':0,'value':100},{'property':'x','time':4,'value':500}]},1)
    store.execute(pid,'set_selection',{'element_ids':[eid]})
    srv,_=start_background(store)
    base=f'http://127.0.0.1:{srv.server_port}'
    errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(**({'executable_path':shutil.which('chromium')} if shutil.which('chromium') else {}))
            page=browser.new_page(viewport={'width':1512,'height':982})
            page.add_init_script("localStorage.setItem('framecore-onboarding-v2', 'done')")
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base)
            page.wait_for_function('document.querySelector("#player").ready')
            assert page.locator('html').get_attribute('lang')=='pl'
            assert page.locator('#export').inner_text()=='Eksport'
            page.click('[data-tab="Shapes"]')
            assert page.locator('[data-icon]').count()==60
            page.click('[data-icon="robot"]')
            page.wait_for_function('document.querySelectorAll(".clip.image").length===1')
            page.locator('.clip.text').click()
            page.click('[data-duplicate]')
            page.wait_for_function('document.querySelectorAll(".clip.text").length===2')
            page.click('#undo')
            page.wait_for_function('document.querySelectorAll(".clip.text").length===1')
            page.locator('.clip.text').click()
            page.click('[data-keyframes]')
            page.fill('#keyframeTo','400')
            page.click('#saveKeyframes')
            page.wait_for_function('!document.querySelector("#modal").open')
            result=store.read(pid)
            assert result['project']['elements'][0]['keyframes'][-1]['value']==400
            page.click('[data-tab="Motion"]')
            assert page.locator('[data-motion]').count()==28
            page.click('#agentTab')
            page.click('[data-inspect]')
            page.locator('#modal').wait_for(state='visible')
            page.click('[data-close]')
            page.click('[data-capture]')
            page.wait_for_selector('img[alt="Klatka filmu"]',timeout=45000)
            assert page.locator('img[alt="Klatka filmu"]').evaluate('el=>el.complete && el.naturalWidth===1080')
            page.click('[data-close]')
            # Inspect every registered motion at non-monotonic times, using the actual compiler/runtime.
            test=browser.new_page(viewport={'width':1080,'height':1920})
            for motion in registry():
                project=store.read(pid)['project'];project['elements']=[project['elements'][0]]
                project['elements'][0]['motion']={'id':motion['id'],'duration':.8}
                test.set_content(compile_project(project))
                test.evaluate('window.__ready')
                test.evaluate('window.seek(2)')
                assert float(test.locator('.fc-element').evaluate('el=>parseFloat(el.style.left)'))==250
                expected=test.locator('.fc-element').get_attribute('style')
                test.evaluate('window.seek(.1)');test.evaluate('window.seek(3)');test.evaluate('window.seek(2)')
                assert test.locator('.fc-element').get_attribute('style')==expected
            assert errors==[]
            browser.close()
    finally:
        srv.shutdown();srv.server_close()


@pytest.mark.browser
def test_creator_pack_offline_ui_fonts_background_and_template(tmp_path):
    from framecore.composition import compile_project
    from framecore.library import manifest
    store=Store(tmp_path/'projects');state=store.create('Zażółć gęślą jaźń','16:9',6)
    pid=state['project']['id'];srv,_=start_background(store);base=f'http://127.0.0.1:{srv.server_port}'
    errors=[];external=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(**({'executable_path':shutil.which('chromium')} if shutil.which('chromium') else {}))
            page=browser.new_page(viewport={'width':1512,'height':982})
            page.add_init_script("localStorage.setItem('framecore-onboarding-v2', 'done')")
            page.on('pageerror',lambda e:errors.append(str(e)))
            def offline(route):
                if route.request.url.startswith(base) or route.request.url.startswith('data:'):route.continue_()
                else:external.append(route.request.url);route.abort()
            page.route('**/*',offline)
            page.goto(base);page.wait_for_function('document.querySelector("#player").ready')
            page.click('[data-tab="Text"]')
            assert page.locator('[data-font]').count()==8
            page.click('[data-text="Twój nagłówek"]')
            page.wait_for_selector('[data-property="style.fontFamily"]')
            page.select_option('[data-property="style.fontFamily"]','Playfair Display')
            page.wait_for_function('document.querySelector("[data-property=\\"style.fontFamily\\"]").value==="Playfair Display"')
            page.click('[data-tab="Library"]')
            assert page.locator('[data-builtin]').count()==87
            page.fill('#librarySearch','rakieta')
            assert page.locator('[data-builtin]').count()==3
            page.click('[data-builtin="fluent-rocket"]')
            page.wait_for_function('document.querySelectorAll(".clip.image").length===1')
            assert store.read(pid)['project']['assets'][0]['provenance']['library_id']=='fluent-rocket'
            page.click('[data-tab="Backgrounds"]')
            assert page.locator('[data-background]').count()==24
            page.click('[data-background="aurora-breath"]')
            page.wait_for_selector('[data-background="aurora-breath"].active')
            page.click('[data-tab="Templates"]')
            assert page.locator('[data-template]').count()==12
            page.click('[data-template="editorial"]')
            page.wait_for_selector('.plan-item')
            page.fill('[data-plan-message="0"]','Zażółć gęślą jaźń')
            page.click('#assemble')
            page.wait_for_selector('[data-apply]')
            page.click('[data-apply]')
            page.wait_for_function('document.querySelectorAll(".clip.text").length===6')
            after=store.read(pid)['project']
            assert after['brand']['font']=='Fraunces' and after['canvas']['backgroundPreset']=='cream'
            assert after['scenes'][0]['message']=='Zażółć gęślą jaźń'
            page.click('#undo')
            page.wait_for_function('document.querySelectorAll(".clip.text").length===1')
            assert store.read(pid)['project']['canvas']['backgroundPreset']=='aurora-breath'
            # Every font is embedded in the composition, loaded with networking blocked.
            test=browser.new_page(viewport={'width':1920,'height':1080});test.route('**/*',offline)
            project=store.read(pid)['project']
            project['elements']=[project['elements'][0]];e=project['elements'][0]
            e.update(text='Zażółć gęślą jaźń',start=0,duration=6,motion=None)
            for f in manifest()['fonts']:
                e['style'].update(fontFamily=f['family'],fontWeight=min(700,f['weight'][1]))
                test.set_content(compile_project(project));test.evaluate('window.__ready')
                faces=test.evaluate('Array.from(document.fonts).filter(f=>f.status==="loaded").map(f=>f.family.replaceAll(\'"\',\'\'))')
                assert f['family'] in faces
            test.evaluate('window.seek(1.2)');first=test.screenshot()
            test.evaluate('window.seek(3.6)');assert test.screenshot()!=first
            test.evaluate('window.seek(1.2)');assert test.screenshot()==first
            assert errors==[] and external==[]
            browser.close()
    finally:srv.shutdown();srv.server_close()

@pytest.mark.browser
def test_capture_does_not_seek_repeatedly_after_media_end(tmp_path):
    import io
    import wave
    from framecore.server import import_asset
    from framecore.composition import compile_project

    data = io.BytesIO()
    with wave.open(data, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b'\0\0' * 8000)
    store = Store(tmp_path / 'projects')
    state = store.create('End of source', duration=4)
    pid = state['project']['id']
    state = import_asset(store, pid, data.getvalue(), 'sound.wav', expected_revision=state['project']['revision'])
    state = store.execute(pid, 'add_audio', {
        'assetId': state['project']['assets'][0]['id'], 'duration': 1,
    }, state['project']['revision'])
    # Imported metadata can outlast the duration decoded by the browser.
    state['project']['assets'][0]['duration'] = 4
    state['project']['elements'][0]['duration'] = 4
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.route('http://media.test/**', lambda route: route.fulfill(
            body=data.getvalue(), content_type='audio/wav'))
        page.set_content(compile_project(state['project'], 'http://media.test/'))
        page.evaluate('window.__ready')
        page.evaluate('window.__CAPTURE__ = true')
        # Once the clamped end position has been reached, subsequent frames
        # must not assign currentTime again and wait for a nonexistent seeked.
        seeks = page.evaluate('''async () => {
            const media=document.querySelector('audio'); let seeks=0;
            Object.defineProperty(media,'currentTime',{get:()=>media.duration-.001,set:()=>seeks++});
            await Promise.race([
                (async()=>{await window.seek(2.1);await window.seek(2.2)})(),
                new Promise((_,reject)=>setTimeout(()=>reject(Error('Redundant seek stalled capture')),1000))
            ]);
            return seeks;
        }''')
        assert seeks == 0
        browser.close()
