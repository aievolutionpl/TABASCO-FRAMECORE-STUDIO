"""Exercise onboarding, local settings and a real UI-to-agent-to-store flow."""
import json
from pathlib import Path
import pytest
from framecore.server import start_background
from framecore.store import Store

def test_onboarding_and_integrated_agent(tmp_path, monkeypatch):
    from playwright.sync_api import sync_playwright
    store=Store(tmp_path/'projects')
    pid=store.create('Browser agent test')['project']['id']
    server,thread=start_background(store)
    responses=iter([
        {'choices':[{'message':{'role':'assistant','content':'','tool_calls':[{'id':'edit','type':'function','function':{'name':'add_text','arguments':json.dumps({'project_id':pid,'expected_revision':0,'text':'Zrobione przez agenta','start':0,'duration':5})}}]}}]},
        {'choices':[{'message':{'role':'assistant','content':'Dodano nagłówek.'}}]},
    ])
    monkeypatch.setattr(server.assistant,'_request',lambda *args:next(responses))
    try:
        with sync_playwright() as pw:
            from vstudio.renderers.html_to_video import launch_browser
            browser=launch_browser(pw,None)
            page=browser.new_page(viewport={'width':1440,'height':1000})
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.locator('#tourDialog').wait_for(state='visible')
            for _ in range(5): page.locator('#tourNext').click()
            assert not page.locator('#tourDialog').is_visible()
            page.locator('#studioConnect').click()
            page.locator('#assistantKey').fill('test-only-key')
            page.locator('#connectionForm button.primary-button').click()
            page.get_by_text('Ustawienia zapisane.',exact=True).wait_for()
            page.locator('[data-close-dialog="connectionDialog"]').click()
            page.locator('#studioAgent').click()
            page.locator('#assistantPrompt').fill('Dodaj nagłówek')
            page.locator('#sendAgent').click()
            page.get_by_text('Dodano nagłówek.',exact=True).wait_for(timeout=20000)
            assert store.read(pid)['project']['elements'][0]['text']=='Zrobione przez agenta'
            assert store.read(pid)['canUndo']
            page.wait_for_function('window.framecoreContext()?.revision === 1')
            page.screenshot(path='output/qa-agent-desktop.png')
            page.locator('#closeAgent').click()
            page.locator('#studioTour').click()
            page.screenshot(path='output/qa-onboarding.png')
            page.locator('[data-close-dialog="tourDialog"]').click()
            page.reload()
            assert not page.locator('#tourDialog').is_visible()
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close();thread.join()
