import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from framecore.agent import AgentService
from framecore.api import API
from framecore.model import EditorError
from framecore.render import RenderJobs
from framecore.server import start_background
from framecore.store import Store

@pytest.fixture
def service(tmp_path):
    store=Store(tmp_path/'projects')
    api=API(store,RenderJobs(store))
    service=AgentService(api,tmp_path/'private'/'settings.json')
    service.save({'provider':'openrouter','model':'test/model','api_key':'test-secret'})
    return service,store.create('Test')['project']['id']

def wait(service, job):
    for _ in range(200):
        result=service.get(job['id'])
        if result['status']!='running': return result
        time.sleep(.01)
    pytest.fail('Agent failed to finish')

def answer(calls=None, content='Gotowe'):
    return {'choices':[{'message':{'role':'assistant','content':content,**({'tool_calls':calls} if calls else {})}}]}

def tool(name,args,id='one'):
    return {'id':id,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}

def test_key_is_private_and_provider_switch_clears_it(service):
    s,pid=service
    assert 'test-secret' not in json.dumps(s.status())
    assert 'test-secret' not in json.dumps(s.api.store.read(pid))
    restored=AgentService(s.api,s.path)
    assert restored.status()['configured']
    restored.save({'provider':'openai','model':'gpt-4.1-mini'})
    assert restored.config['api_key']==''
    with pytest.raises(EditorError): s.save({'provider':'custom-url'})

def test_agent_edits_with_real_history_and_confines_project(service,monkeypatch):
    s,pid=service
    other=s.api.store.create('Other')['project']['id']
    replies=iter([answer([tool('add_text',{'project_id':other,'expected_revision':0,'text':'Agent działa','start':0,'duration':3})]),answer()])
    monkeypatch.setattr(s,'_request',lambda *args:next(replies))
    result=wait(s,s.start(pid,'Dodaj tekst'))
    assert result['status']=='complete'
    state=s.api.store.read(pid)
    assert state['project']['elements'][0]['text']=='Agent działa'
    assert state['canUndo']
    assert not s.api.store.read(other)['project']['elements']
    assert 'test-secret' not in json.dumps(result)

def test_stale_revision_and_forbidden_tools_do_not_mutate(service,monkeypatch):
    s,pid=service
    s.api.store.execute(pid,'add_text',{'text':'Human','duration':3},0,'human')
    replies=iter([answer([tool('add_text',{'expected_revision':0,'text':'Stale'}),tool('add_asset',{'source_file':'/private/key'},'two')]),answer()])
    monkeypatch.setattr(s,'_request',lambda *args:next(replies))
    result=wait(s,s.start(pid,'Zmień'))
    assert all(not event['ok'] for event in result['events'])
    assert len(s.api.store.read(pid)['project']['elements'])==1

def test_provider_error_and_step_limit(service,monkeypatch):
    s,pid=service
    def fail(*args): raise EditorError('Limit dostawcy','provider_error')
    monkeypatch.setattr(s,'_request',fail)
    assert wait(s,s.start(pid,'Test'))['status']=='failed'
    monkeypatch.setattr(s,'_request',lambda *args:answer([tool('get_project',{})]))
    result=wait(s,s.start(pid,'Test'))
    assert len(result['events'])==16
    assert 'limit' in result['reply']

def test_cancel_and_busy(service,monkeypatch):
    import threading
    s,pid=service
    gate=threading.Event()
    monkeypatch.setattr(s,'_request',lambda *args:(gate.wait(2),answer([tool('add_text',{'expected_revision':0,'text':'No'})]))[1])
    job=s.start(pid,'Test')
    with pytest.raises(EditorError): s.start(pid,'Another')
    s.cancel(job['id']);gate.set()
    assert wait(s,job)['status']=='cancelled'
    assert not s.api.store.read(pid)['project']['elements']

def test_http_requires_token_and_does_not_return_secret(tmp_path):
    server,thread=start_background(Store(tmp_path/'projects'))
    base=f'http://127.0.0.1:{server.server_port}'
    data=json.dumps({'provider':'openrouter','model':'test/model','api_key':'hidden-key'}).encode()
    try:
        with pytest.raises(HTTPError) as exc:
            urlopen(Request(base+'/api/assistant/settings',data=b'',headers={'Content-Type':'application/json'}))
        assert exc.value.code==403
        req=Request(base+'/api/assistant/settings',data=data,headers={'Content-Type':'application/json','X-Studio-Token':server.token,'Origin':base})
        assert 'hidden-key' not in urlopen(req).read().decode()
        assert 'hidden-key' not in urlopen(base+'/api/assistant/status').read().decode()
    finally:
        server.shutdown();server.server_close();thread.join()
