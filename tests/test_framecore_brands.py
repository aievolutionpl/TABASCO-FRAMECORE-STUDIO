from copy import deepcopy
import io
import json
import shutil
import time
import threading

from PIL import Image
import pytest
from playwright.sync_api import sync_playwright, expect
from framecore.brands import BrandLibrary, DEFAULT, validate_profile
from framecore.model import EditorError
from framecore.server import start_background
from framecore.store import Store
from framecore.api import API
from framecore.agent_control import AgentControl


def picture():
    stream=io.BytesIO();Image.new('RGB',(80,40),'red').save(stream,'PNG');return stream.getvalue()


def setup(tmp_path):
    store=Store(tmp_path/'projects');library=BrandLibrary(store)
    b=library.save({**deepcopy(DEFAULT),'name':'Firma A','about':'Serwis pomp ciepła',
        'products':[{'name':'Przegląd','description':'Przegląd instalacji','url':''}],
        'sources':[{'url':'https://example.com','note':'Brief klienta'}]})
    pid=store.create('Film dla marki','16:9',5)['project']['id']
    store.execute(pid,'add_text',{'text':'Oferta','duration':5},0)
    return store,library,b,pid


def test_profiles_persist_conflict_and_snapshot_assets_are_independent(tmp_path):
    store,library,b,pid=setup(tmp_path)
    b=library.upload(b['id'],1,picture(),'logo.png','logo')
    b=library.upload(b['id'],2,picture(),'referencja.png','reference')
    state=library.apply(b['id'],3,pid,1,True)
    p=state['project'];assert p['revision']==2 and len(p['assets'])==2
    assert p['brand']['name']=='Firma A' and p['elements'][0]['style']['fontFamily']=='Manrope'
    assert p['brand']['logoAssetId']==p['assets'][0]['id']
    assert store.context(pid)['companyBrain']['offer']==b['offer']
    assert p['brandProfile']['sources']==b['sources']
    assert BrandLibrary(Store(store.root)).get(b['id'])==b
    fields={k:b[k] for k in DEFAULT};fields['name']='Firma A po rebrandingu'
    latest=library.save(fields,b['id'],3)
    with pytest.raises(EditorError,match='zmienił'):library.save(fields,b['id'],3)
    with pytest.raises(EditorError,match='zmienił'):library.delete(b['id'],3)
    with pytest.raises(EditorError,match='zmienił'):library.upload(b['id'],3,picture(),'new.png','logo')
    assert latest['version']==4
    library.delete(b['id'],4)
    assert library.list()=={'profiles':[]}
    unchanged=store.read(pid)['project'];assert unchanged==p
    assert all((store.directory(pid)/a['file']).read_bytes()==picture() for a in p['assets'])
    undo=store.execute(pid,'undo',{},2)
    assert 'brandProfile' not in undo['project'] and undo['project']['assets']==[]
    redo=store.execute(pid,'redo',{},3)
    assert redo['project']['brandProfile']==p['brandProfile']
    assert len(store.list())==1


def test_apply_conflict_cleanup_validation_and_removed_asset(tmp_path):
    store,library,b,pid=setup(tmp_path)
    b=library.upload(b['id'],1,picture(),'product.png','product')
    before=store.read(pid)
    with pytest.raises(EditorError):library.apply(b['id'],2,pid,0)
    assert list((store.directory(pid)/'assets').iterdir())==[]
    assert store.read(pid)==before
    with pytest.raises(EditorError):library.upload(b['id'],2,b'<svg onload="evil"/>','bad.png','logo')
    with pytest.raises(EditorError):library.upload(b['id'],2,picture(),'../logo.svg','logo')
    with pytest.raises(EditorError):validate_profile({**DEFAULT,'website':'file:///etc/passwd'})
    with pytest.raises(EditorError):validate_profile({**DEFAULT,'font':'Unavailable'})
    with pytest.raises(EditorError):validate_profile({**DEFAULT,'sources':[{'url':'javascript:evil','note':'x'}]})
    with pytest.raises(EditorError):library.get('../escape')
    (library.directory(b['id'])/b['assets'][0]['file']).write_bytes(b'tampered')
    with pytest.raises(EditorError,match='zmienił zawartość'):library.apply(b['id'],2,pid,1)
    b=library.remove_asset(b['id'],2,b['assets'][0]['id'])
    assert b['version']==3 and b['assets']==[]
    assert list((library.directory(b['id'])/'assets').iterdir())==[]


def test_mcp_tools_and_company_brain_reach_editing_agent(tmp_path,monkeypatch):
    store,library,b,pid=setup(tmp_path);api=API(store,None)
    tools={t['name']:t['inputSchema'] for t in api.tools()}
    assert 'source_file' in tools['upload_brand_asset']['required']
    assert tools['list_brand_profiles']['required']==[]
    assert 'project_id' not in tools['save_brand_profile']['required']
    assert set(tools['apply_brand_profile']['required'])=={'project_id','expected_revision','brand_id','expected_version'}
    imports=store.root.parent/'imports';imports.mkdir()
    image=imports/'reference.png';image.write_bytes(picture())
    uploaded=api.call('upload_brand_asset',{'brand_id':b['id'],'expected_version':1,'source_file':str(image),'role':'reference'})
    assert len(uploaded['assets'])==1
    with pytest.raises(EditorError):api.call('upload_brand_asset',{'brand_id':b['id'],'expected_version':2,'source_file':str(tmp_path/'outside.png')})
    library.apply(b['id'],2,pid,1)
    c=AgentControl(store);c.connect('openrouter','openai/test','test-key')
    seen=[]
    def reply(_,text,event):seen.append(json.loads(text));return {'message':'Brak zmian','commands':[]}
    monkeypatch.setattr(c,'_request',reply)
    c.start(pid,2,'Przygotuj reklamę')
    deadline=time.monotonic()+5
    while c.status()['task']['status'] in {'queued','running'} and time.monotonic()<deadline:time.sleep(.02)
    assert seen[0]['companyBrain']['about']=='Serwis pomp ciepła'
    assert seen[0]['companyBrain']['products'][0]['name']=='Przegląd'
    assert 'test-key' not in json.dumps(seen)


def test_agent_draft_is_reviewable_not_saved_and_cancelled(tmp_path,monkeypatch):
    store,library,b,pid=setup(tmp_path);c=AgentControl(store);c.connect('openrouter','openai/test','test-key')
    draft=deepcopy(DEFAULT);draft.update(name='Firma A',about='Firma usługowa',researchNotes='Oferta wymaga potwierdzenia')
    monkeypatch.setattr(c,'_request',lambda *_:json.dumps(draft))
    c.start_brand({k:b[k] for k in DEFAULT},'Brief firmy i źródło https://example.com')
    deadline=time.monotonic()+5
    while c.status()['task']['status'] in {'queued','running'} and time.monotonic()<deadline:time.sleep(.02)
    assert c.status()['task']['status']=='draft'
    assert c.status()['task']['draft']['about']=='Firma usługowa'
    assert library.get(b['id'])==b and store.read(pid)['project']['revision']==1
    monkeypatch.setattr(c,'_request',lambda *_: '{"website":"javascript:bad"}')
    c.start_brand({k:b[k] for k in DEFAULT},'Źródła')
    deadline=time.monotonic()+5
    while c.status()['task']['status'] in {'queued','running'} and time.monotonic()<deadline:time.sleep(.02)
    assert c.status()['task']['status']=='failed'
    entered=threading.Event();release=threading.Event()
    def delayed(*_):entered.set();release.wait(3);return draft
    monkeypatch.setattr(c,'_request',delayed)
    c.start_brand({k:b[k] for k in DEFAULT},'Źródła');assert entered.wait(2)
    c.stop();release.set();time.sleep(.05)
    assert c.status()['task']['status']=='cancelled' and 'draft' not in c.status()['task']
    assert library.get(b['id'])==b


@pytest.mark.browser
def test_company_brain_settings_upload_apply_research_and_mobile(tmp_path,monkeypatch):
    store=Store(tmp_path/'projects');pid=store.create('Film','16:9',5)['project']['id']
    srv,_=start_background(store);errors=[]
    draft=deepcopy(DEFAULT);draft.update(name='Usługi Test',about='Opis od agenta',researchNotes='Do weryfikacji')
    srv.agent.connect('openrouter','openai/test','fake-key')
    monkeypatch.setattr(srv.agent,'_request',lambda *_:draft)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(**({'executable_path':shutil.which('chromium')} if shutil.which('chromium') else {}))
            page=browser.new_page(viewport={'width':1512,'height':982});page.on('pageerror',lambda e:errors.append(str(e)))
            base=f'http://127.0.0.1:{srv.server_port}';page.goto(base)
            page.wait_for_function('document.querySelector("#player").ready')
            page.click('#settings');page.fill('[data-company-field="name"]','Usługi Test')
            page.fill('[data-company-field="about"]','Montaż i serwis')
            page.click('[data-company-add="products"]')
            page.fill('[data-company-entry="products"] [data-entry-field="name"]','Konsultacja')
            page.fill('[data-company-entry="products"] [data-entry-field="description"]','Dobór instalacji')
            page.click('[data-company-add="sources"]')
            page.fill('[data-company-entry="sources"] [data-entry-field="url"]','https://example.com')
            page.fill('[data-company-entry="sources"] [data-entry-field="note"]','Brief demonstracyjny')
            page.click('[data-company="save"]');page.locator('#companyUpload').wait_for()
            page.locator('#companyUpload').set_input_files({'name':'logo.png','mimeType':'image/png','buffer':picture()})
            page.locator('.company-asset').wait_for()
            assert page.request.get(base+'/api/brands').json()['profiles'][0]['assets'][0]['role']=='logo'
            page.click('[data-company="apply"]');page.locator('#modal').wait_for(state='hidden')
            p=store.read(pid)['project'];assert p['brandProfile']['name']=='Usługi Test' and len(p['assets'])==1
            assert p['brandProfile']['products'][0]['name']=='Konsultacja'
            assert p['brandProfile']['sources'][0]['url']=='https://example.com'
            page.click('#settings');page.locator('details summary').click();page.fill('#companyResearch','Firma zajmuje się instalacjami. https://example.com')
            page.click('[data-company="research"]');page.locator('[data-company="draft"]').wait_for(state='visible')
            page.click('[data-company="draft"]');expect(page.locator('[data-company-field="about"]')).to_have_value('Opis od agenta')
            assert BrandLibrary(store).list()['profiles'][0]['about']=='Montaż i serwis'
            page.click('[data-company="save"]');page.locator('#companyUpload').wait_for()
            assert BrandLibrary(store).list()['profiles'][0]['about']=='Opis od agenta'
            assert store.read(pid)['project']['brandProfile']['about']=='Montaż i serwis'
            assert page.request.post(base+'/api/brand-upload/'+p['brandProfile']['id']+'?version=1&name=x.png',data=picture()).status==403
            assert page.request.post(base+'/api/command',data={'name':'save_brand_profile','args':{'profile':DEFAULT}}).status==403
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert page.locator('[data-company="save"]').is_visible()
            page.screenshot(path=str(tmp_path/'company-brain-mobile.png'))
            page.click('[data-close]');page.locator('#modal').wait_for(state='hidden')
            for button in ('#settings','#newProject','#export'):
                bounds=page.locator(button).bounding_box()
                assert bounds and bounds['x']>=0 and bounds['x']+bounds['width']<=390
            page.click('#settings');page.locator('#companySelect').wait_for()
            assert not errors
            browser.close()
    finally:srv.shutdown();srv.server_close()
