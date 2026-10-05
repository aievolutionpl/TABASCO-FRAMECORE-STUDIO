import json
import shutil
import sys
import threading
import time
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright
from framecore.agent_control import AgentControl
from framecore.model import EditorError
from framecore.server import start_background
from framecore.store import Store


def setup(tmp_path):
    store=Store(tmp_path/'projects');pid=store.create('Agent','16:9',5)['project']['id']
    store.execute(pid,'add_text',{'text':'Przed','duration':5},0)
    eid=store.read(pid)['project']['elements'][0]['id']
    store.execute(pid,'set_selection',{'element_ids':[eid]})
    controller=AgentControl(store);controller.connect('openrouter','openai/test-model','test-key-not-real')
    return store,controller,pid,eid


def wait(controller):
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        s=controller.status()['task']
        if s and s['status'] not in {'queued','running'}:return s
        time.sleep(.02)
    raise AssertionError('Agent nie zakończył zadania')


def result(eid=None,text='Po zmianie'):
    return {'message':'Zmieniam nagłówek','commands':[{'name':'set_property','args':{'property':'text','value':text,**({'element_id':eid} if eid else {})}}]}


def test_proposals_auto_apply_and_undo_use_same_history(tmp_path,monkeypatch):
    store,c,pid,eid=setup(tmp_path)
    monkeypatch.setattr(c,'_request',lambda *_:result(eid))
    c.start(pid,1,'Popraw nagłówek')
    first=wait(c);assert first['status']=='proposed'
    assert store.read(pid)['project']['elements'][0]['text']=='Przed'
    assert store.read(pid)['project']['revision']==1
    store.execute(pid,'apply_proposal',{'proposal_id':first['proposal_id']},1,'human')
    c.start(pid,2,'Jeszcze popraw',True);assert wait(c)['status']=='applied'
    assert store.read(pid)['project']['revision']==3
    assert store.read(pid)['history'][-1]['actor']=='agent'
    store.execute(pid,'undo',{},3);assert store.read(pid)['project']['revision']==4
    assert len(store.read(pid)['history'])==3
    assert 'apiKey' not in json.dumps(c.status()) and 'test-key' not in json.dumps(c.status())
    c.stop(disconnect=True);assert not c.status()['connected']


def test_conflicts_cancel_and_frozen_selection(tmp_path,monkeypatch):
    store,c,pid,eid=setup(tmp_path);entered=threading.Event();release=threading.Event()
    def provider(*_):entered.set();release.wait(4);return result()
    monkeypatch.setattr(c,'_request',provider)
    c.start(pid,1,'Przejmij stery',True);assert entered.wait(2)
    store.execute(pid,'add_text',{'text':'Nowy cel'},1);second=store.read(pid)['project']['elements'][-1]['id']
    store.execute(pid,'set_selection',{'element_ids':[second]})
    release.set();assert wait(c)['errorCode']=='revision_conflict'
    assert store.read(pid)['project']['elements'][0]['text']=='Przed'
    entered.clear();release.clear();c.start(pid,2,'Zmień zaznaczony',True);assert entered.wait(2)
    store.execute(pid,'set_selection',{'element_ids':[eid]})
    release.set();assert wait(c)['status']=='applied'
    # Changing selection did not redirect the model's mutation to another element.
    elements=store.read(pid)['project']['elements'];assert elements[0]['text']=='Przed' and elements[1]['text']=='Po zmianie'
    entered.clear();release.clear();c.start(pid,3,'Jeszcze',True);assert entered.wait(2)
    c.stop(disconnect=True);release.set();time.sleep(.15)
    assert c.status()['task']['status']=='cancelled' and store.read(pid)['project']['revision']==3


def test_invalid_commands_are_atomic_and_provider_errors_hide_key(tmp_path,monkeypatch):
    store,c,pid,eid=setup(tmp_path);before=store.read(pid)
    invalid=result(eid);invalid['commands'].append({'name':'set_property','args':{'element_id':eid,'property':'opacity','value':2}})
    monkeypatch.setattr(c,'_request',lambda *_:invalid)
    c.start(pid,1,'Niepoprawna odpowiedź',True);assert wait(c)['status']=='failed'
    assert store.read(pid)==before
    monkeypatch.setattr(c,'_request',lambda *_:{'message':'Uruchom kod','commands':[{'name':'export','args':{}}]})
    c.start(pid,1,'Wyjście poza kontrakt',True);assert wait(c)['errorCode']=='agent_invalid_output'
    assert store.read(pid)==before
    def failure(*_):raise RuntimeError('Authorization: Bearer test-key-not-real')
    monkeypatch.setattr(c,'_request',failure);c.start(pid,1,'Awaria')
    task=wait(c);assert 'test-key' not in json.dumps(task)
    assert all('test-key' not in f.read_text() for f in store.root.rglob('*.json'))


def test_openrouter_request_and_real_cli_process_adapters(tmp_path,monkeypatch):
    store,c,pid,eid=setup(tmp_path)
    import framecore.agent_control as module
    seen=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,_):return json.dumps({'choices':[{'message':{'content':json.dumps(result(eid))}}]}).encode()
    def transport(request,timeout):
        seen.append(request);assert request.full_url=='https://openrouter.ai/api/v1/chat/completions';return Response()
    monkeypatch.setattr(module,'urlopen',transport)
    c.start(pid,1,'Przez OpenRouter',True);assert wait(c)['status']=='applied'
    payload=json.loads(seen[0].data)
    assert payload['model']=='openai/test-model'
    assert 'test-key' not in json.dumps(payload)
    assert seen[0].headers['Authorization']=='Bearer test-key-not-real'
    # Execute genuine subprocesses with fake deterministic model output, not paid sessions.
    for provider in ('codex','claude'):
        script=tmp_path/provider
        script.write_text('#!'+sys.executable+'\nimport sys,json\nfrom pathlib import Path\np=json.loads(sys.stdin.read())\nassert p["project"]["revision"]==2\na='+repr(result(eid))+'\nif "--output-last-message" in sys.argv:\n Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps(a))\nelse: print(json.dumps({"result":json.dumps(a)}))\n')
        script.chmod(0o755)
        real_which=shutil.which
        with monkeypatch.context() as scoped:
            scoped.setattr(module.shutil,'which',lambda name: str(script) if name==provider else real_which(name))
            c.connect(provider)
            answer=c._request(c.connection,'{"project":{"revision":2}}',threading.Event())
            assert module.parse_result(answer)==result(eid)


    # Windows npm .cmd launcher is resolved to Node + JS, without cmd.exe quoting.
    prefix=tmp_path/'npm with spaces';prefix.mkdir();wrapper=prefix/'codex.cmd';wrapper.write_text('npm launcher')
    script=prefix/'node_modules/@openai/codex/bin/codex.js';script.parent.mkdir(parents=True)
    script.write_text("const fs=require('fs');const args=process.argv;let data='';process.stdin.on('data',c=>data+=c);process.stdin.on('end',()=>{const p=JSON.parse(data);if(p.project.revision!==2)process.exit(2);fs.writeFileSync(args[args.indexOf('--output-last-message')+1],JSON.stringify("+json.dumps(result(eid))+"));});")
    real_which=shutil.which
    with monkeypatch.context() as scoped:
        scoped.setattr(module.shutil,'which',lambda name:str(wrapper) if name=='codex' else real_which(name))
        c.connect('codex')
        assert module.cli_entry('codex')==[real_which('node'),str(script)]
        assert module.parse_result(c._request(c.connection,'{"project":{"revision":2}}',threading.Event()))==result(eid)


@pytest.mark.browser
def test_dashboard_connection_task_stop_and_key_not_stored(tmp_path,monkeypatch):
    store,c,pid,eid=setup(tmp_path);srv,_=start_background(store);errors=[]
    monkeypatch.setattr(srv.agent,'_request',lambda *_:result(eid,'Nagłówek od agenta'))
    base=f'http://127.0.0.1:{srv.server_port}'
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(**({'executable_path':shutil.which('chromium')} if shutil.which('chromium') else {}))
            page=browser.new_page(viewport={'width':1512,'height':982});page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base);page.wait_for_function('document.querySelector("#player").ready')
            page.click('#agentTab');page.click('[data-connect]')
            page.fill('#agentModel','openai/test-model');page.fill('#agentApiKey','test-key-not-real');page.click('[data-agent-action="connect"]')
            page.locator('#modal').wait_for(state='hidden');page.locator('#agentConnectionStatus').wait_for();page.fill('#agentPrompt','Zmień nagłówek')
            page.check('#agentAutoApply');assert page.locator('#agentPrompt').input_value()=='Zmień nagłówek'
            page.click('[data-agent-action="run"]')
            page.wait_for_function('document.querySelector("#agentTaskStatus").textContent.includes("Zmiany zastosowane")',timeout=8000)
            assert store.read(pid)['project']['elements'][0]['text']=='Nagłówek od agenta'
            assert page.evaluate('JSON.stringify(localStorage)').find('test-key')==-1
            page.click('#undo');assert store.read(pid)['project']['elements'][0]['text']=='Przed'
            # Same-origin token boundary covers billing-triggering routes.
            unauth=page.request.post(base+'/api/agent/run',data={'project_id':pid,'prompt':'x'})
            assert unauth.status==403
            page.set_viewport_size({'width':390,'height':844});page.click('[data-tab="AI"]')
            assert page.locator('[data-agent-action="run"]').is_visible()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(tmp_path/'agent-mobile.png'))
            assert not errors
            browser.close()
    finally:srv.shutdown();srv.server_close()
