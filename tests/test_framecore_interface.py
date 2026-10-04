"""Wygoda edycji: ulubione, kolekcje, wyrównanie, podgląd i panele klawiaturą."""
import shutil
import time
import pytest
from playwright.sync_api import sync_playwright
from framecore.server import start_background
from framecore.store import Store


@pytest.mark.browser
def test_polished_interface_editing_and_mobile_keyboard(tmp_path):
    store=Store(tmp_path/'projects');p=store.create('Test interfejsu',duration=6)['project']
    pid=p['id'];p=store.execute(pid,'add_text',{'text':'Zażółć gęślą jaźń','x':100,'y':100,'width':600,'height':200,'duration':4},0)['project']
    eid=p['elements'][0]['id'];store.execute(pid,'set_selection',{'element_ids':[eid]})
    srv,_=start_background(store);base=f'http://127.0.0.1:{srv.server_port}';errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(**({'executable_path':shutil.which('chromium')} if shutil.which('chromium') else {}))
            page=browser.new_page(viewport={'width':1512,'height':982})
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base);page.wait_for_function('document.querySelector("#player").ready')
            assert page.locator('.wordmark-lockup').evaluate('el=>el.complete && el.naturalWidth>0')
            page.click('[data-align="center"]')
            page.wait_for_function('document.querySelector("[data-property=x]").value==="240"')
            assert store.read(pid)['project']['elements'][0]['x']==240
            page.click('[data-align="middle"]')
            page.wait_for_function('document.querySelector("[data-property=y]").value==="860"')
            page.click('#undo')
            page.wait_for_function('document.querySelector("[data-property=y]").value==="100"')
            page.click('[data-tab="Library"]')
            page.click('[data-favorite="fluent-rocket"]')
            assert page.locator('[data-favorite="fluent-rocket"]').get_attribute('aria-pressed')=='true'
            assert store.read(pid)['project']['revision']==4  # preferences do not edit the project
            page.click('[data-library-kind="favorite"]')
            assert page.locator('[data-builtin]').count()==1
            page.reload();page.wait_for_function('document.querySelector("#player").ready')
            page.click('[data-tab="Library"]');page.click('[data-library-kind="favorite"]')
            assert page.locator('[data-builtin]').count()==1
            page.click('[data-library-kind="all"]');page.select_option('#libraryCollection','Tabler')
            assert page.locator('[data-builtin]').count()==24
            page.click('[data-tab="Brand"]');page.click('[data-use-studio-logo]')
            page.wait_for_function('document.querySelectorAll(".clip.image").length===1')
            branded=store.read(pid)['project']
            assert branded['brand']['logoAssetId']==branded['assets'][-1]['id']
            assert branded['elements'][-1]['duration']==6
            page.click('#undo')
            page.wait_for_function('document.querySelectorAll(".clip.image").length===0')
            assert store.read(pid)['project']['brand']['logoAssetId'] is None
            # A rapid duplicate must wait for a slow selection request.
            execute=store.execute
            def slow_selection(pid,name,*args,**kwargs):
                if name=='set_selection':time.sleep(.2)
                return execute(pid,name,*args,**kwargs)
            store.execute=slow_selection
            page.evaluate('(id)=>{document.querySelector(`[data-clip="${id}"]`).click();document.querySelector("[data-duplicate]").click();}',eid)
            page.wait_for_function('document.querySelectorAll(".clip.text").length===2')
            assert store.read(pid)['project']['elements'][-1]['text']=='Zażółć gęślą jaźń'
            page.click('#undo');page.wait_for_function('document.querySelectorAll(".clip.text").length===1')
            store.execute=execute
            page.locator(f'[data-clip="{eid}"]').click()
            page.click('[data-tab="Motion"]');page.click('[data-motion="float"]')
            page.wait_for_function('document.querySelector("#play").getAttribute("aria-label")==="Pauza"')
            assert store.read(pid)['project']['elements'][0]['motion']['id']=='float'
            page.wait_for_function('document.querySelector("#play").getAttribute("aria-label")==="Odtwarzaj"')
            page.set_viewport_size({'width':390,'height':844})
            page.click('[data-tab="Library"]')
            assert page.locator('.library[data-panel-open]').is_visible()
            assert page.locator('.library').get_attribute('aria-modal')=='true'
            assert page.locator('.library').bounding_box()['height']>700
            assert page.locator('.workspace').evaluate('el=>el.inert')
            page.get_by_role('button',name='Zamknij bibliotekę').focus();page.keyboard.press('Tab')
            assert page.evaluate('document.activeElement.id')=='librarySearch'
            page.keyboard.press('Escape')
            assert page.locator('[data-panel-open]').count()==0
            assert page.locator('[data-tab="Library"]').evaluate('el=>el===document.activeElement')
            assert not page.locator('.workspace').evaluate('el=>el.inert')
            page.click('#openInspector')
            assert page.locator('.inspector[data-panel-open]').is_visible()
            panel=page.locator('.inspector').bounding_box();content=page.locator('#inspectorContent').bounding_box()
            assert panel['height']>700
            assert content['x']>=panel['x'] and content['x']+content['width']<=panel['x']+panel['width']
            assert page.locator('[data-property=\"style.fontFamily\"]').is_visible()
            page.locator('.inspector').screenshot(path=str(tmp_path/'mobile-properties.png'))
            page.keyboard.press('Escape')
            assert page.locator('#openInspector').evaluate('el=>el===document.activeElement')
            page.click('#projectMenu');page.locator('[data-project]').wait_for();page.click('[data-close]')
            page.click('#newProject');page.locator('#newName').wait_for();page.click('[data-close]')
            for width,height in [(320,760),(390,844),(900,900),(1512,982)]:
                page.set_viewport_size({'width':width,'height':height})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            # Reduced motion stops decorative card animation.
            page.emulate_media(reduced_motion='reduce');page.click('[data-tab="Motion"]')
            assert page.locator('[data-motion="float"] .motion-demo').evaluate('el=>getComputedStyle(el).animationName')=='none'
            assert errors==[]
            browser.close()
    finally:srv.shutdown();srv.server_close()
