from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from playwright.sync_api import sync_playwright


def test_marketing_page_mobile_downloads_video_and_reduced_motion(tmp_path):
    root=Path(__file__).resolve().parents[1]
    out=tmp_path/'site'
    subprocess.run([sys.executable,str(root/'scripts/build-site.py'),'--out',str(out)],check=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(out)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    errors=[]
    release={'tag_name':'v0.3.0-desktop.1','name':'FrameCore desktop preview','draft':False,'assets':[
        {'name':'FrameCore-windows-x64-setup.exe','browser_download_url':'https://github.com/aievolutionpl/TABASCO-FRAMECORE-STUDIO/releases/download/v0.3.0-desktop.1/windows.exe'},
        {'name':'FrameCore-macos-arm64.dmg','browser_download_url':'https://github.com/aievolutionpl/TABASCO-FRAMECORE-STUDIO/releases/download/v0.3.0-desktop.1/apple.dmg'},
        {'name':'FrameCore-macos-x64.dmg','browser_download_url':'https://github.com/aievolutionpl/TABASCO-FRAMECORE-STUDIO/releases/download/v0.3.0-desktop.1/intel.dmg'}]}
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'))
            page=browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('https://api.github.com/**',lambda route:route.fulfill(json=[release]))
            page.goto(f'http://127.0.0.1:{server.server_port}/');page.wait_for_function('document.fonts.status==="loaded"')
            page.locator('#windowsDownload').get_by_text('Pobierz dla Windows').wait_for()
            assert page.locator('#macDownload').get_attribute('href').endswith('apple.dmg')
            assert page.locator('#macIntel').get_attribute('href').endswith('intel.dmg')
            for width in [1440,1050,760,390,320]:
                page.set_viewport_size({'width':width,'height':900})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
            page.get_by_text('Czy mogę edytować film po pracy agenta?',exact=False).click()
            assert page.locator('details[open]').count()==1
            page.emulate_media(reduced_motion='reduce')
            assert page.locator('.art-spark').evaluate('n=>getComputedStyle(n).animationName')=='none'
            page.locator('video').evaluate('v=>v.load()');page.wait_for_function('document.querySelector("video").readyState>=2')
            assert page.locator('video').evaluate('v=>v.duration')==21
            assert not errors
            browser.close()
    finally:server.shutdown();server.server_close();thread.join()
