"""Acceptance of the actual frozen app: server, data, MCP, MP4 import and export."""
import argparse
import json
import os
import traceback
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--app',required=True);parser.add_argument('--engine',required=True);args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='framecore-package-') as temporary:
        root=Path(temporary);projects=root/'projects';imports=root/'imports';imports.mkdir()
        with (root/'app.log').open('w') as log:
            ready=root/'ready.json'
            process=subprocess.Popen([args.app,'--headless','--root',str(projects),'--ready-file',str(ready)],stdout=log,stderr=subprocess.STDOUT)
            try:
                deadline=time.monotonic()+120;url=None
                while time.monotonic()<deadline:
                    text=(root/'app.log').read_text(encoding='utf-8',errors='replace')
                    if ready.is_file():url=json.loads(ready.read_text())['url'];break
                    if process.poll() is not None:raise RuntimeError(text)
                    time.sleep(.2)
                if not url:raise RuntimeError('Packaged server did not become ready')
                with urlopen(url,timeout=20) as response:html=response.read().decode()
                token=re.search(r"window.STUDIO_TOKEN='([^']+)'",html).group(1)
                def request(path,data=None):
                    req=Request(url+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Studio-Token':token})
                    with urlopen(req,timeout=60) as response:return json.load(response)
                runtime=request('api/runtime');assert runtime['ready'],runtime
                def call(name,params):return request('api/command',{'name':name,'args':params})
                state=call('create_project',{'name':'Packaged acceptance','format':'16:9','duration':1});pid=state['project']['id']
                def edit(name,**values):
                    nonlocal state
                    state=call(name,{'project_id':pid,'expected_revision':state['project']['revision'],**values});return state
                edit('set_project_fps',fps=6)
                # Build an H.264/AAC source using the tools shipped with the app.
                config=request('api/mcp-config')['mcpServers']['framecore']
                assert Path(config['command']).resolve()==Path(args.engine).resolve(),config
                native_candidates=list(Path(args.app).parent.rglob('ffmpeg.exe' if Path(args.app).suffix=='.exe' else 'ffmpeg'))
                if not native_candidates:
                    native_candidates=list(Path(args.app).parents[1].rglob('ffmpeg'))
                ffmpeg=next(p for p in native_candidates if p.is_file())
                source=imports/'codec-test.mp4'
                subprocess.run([str(ffmpeg),'-y','-v','error','-f','lavfi','-i','color=c=orange:s=160x90:r=6:d=1',
                    '-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(source)],check=True)
                edit('add_asset',source_file=str(source));aid=state['project']['assets'][-1]['id']
                edit('add_video',assetId=aid,start=0,duration=1,x=0,y=0,width=1920,height=1080,motion=None)
                edit('add_audio',assetId=aid,start=0,duration=1)
                before=state['project']['revision'];job=call('render',{'project_id':pid,'expected_revision':before,'quality':'draft'})
                deadline=time.monotonic()+600
                while time.monotonic()<deadline:
                    job=request('api/job/'+job['id'])
                    if job['status'] in {'complete','failed'}:break
                    time.sleep(1)
                assert job['status']=='complete',job
                assert request('api/project/'+pid)['project']['revision']==before
                assert (projects/pid/'state.json').is_file()
                assert (projects/pid/'exports'/job['id']/'framecore.mp4').stat().st_size>1000
                messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}},
                          {'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}}]
                result=subprocess.run([args.engine,'--mcp','--root',str(projects)],input=''.join(json.dumps(m)+'\n' for m in messages),capture_output=True,text=True,timeout=60,check=True)
                replies=[json.loads(line) for line in result.stdout.splitlines()]
                assert 'replace_clip_asset' in {t['name'] for t in replies[-1]['result']['tools']}
                print(json.dumps({'packaged_app':'ready','bundled_tools':True,'h264_aac_import_and_export':'passed','stdio_mcp':'passed','project_saved':True}))
            finally:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':
    try:
        main()
    except Exception:
        if os.environ.get('GITHUB_ACTIONS')=='true':
            detail=traceback.format_exc().replace('%','%25').replace('\r','%0D').replace('\n','%0A')
            print('::error title=Frozen package acceptance::'+detail)
        raise
