"""Acceptance slice: upload -> storyboard -> live MCP -> undo -> actual MP4."""
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

import pytest
from PIL import Image
from playwright.sync_api import sync_playwright

from framecore.server import start_background
from framecore.store import Store

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
            browser=pw.chromium.launch(**({'executable_path':shutil.which('chromium')} if shutil.which('chromium') else {}))
            page=browser.new_page(viewport={'width':1512,'height':982})
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
            page.click('#startExport')
            page.wait_for_selector('a[href$="framecore.mp4"]',timeout=180000)
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
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base)
            page.wait_for_function('document.querySelector("#player").ready')
            assert page.locator('html').get_attribute('lang')=='pl'
            assert page.locator('#export').inner_text()=='Eksport'
            page.click('[data-tab="Shapes"]')
            assert page.locator('[data-icon]').count()==12
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
            assert page.locator('[data-motion]').count()==20
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
