"""FrameCore's shared project/history contract and real transport boundaries."""
import io
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from PIL import Image

from framecore.api import API
from framecore.commands import storyboard
from framecore.composition import compile_project
from framecore.model import EditorError
from framecore.render import RenderJobs
from framecore.server import import_asset, start_background
from framecore.store import Store

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def fc(tmp_path):
    store = Store(tmp_path / "projects")
    state = store.create("Product reel")
    pid = state["project"]["id"]
    state = store.execute(pid, "add_text", {"text": "Hello", "start": 2, "duration": 4}, 0)
    return store, pid, state["project"]["elements"][0]["id"]


def test_human_agent_history_survives_restart_and_branching(fc):
    store, pid, eid = fc
    store.execute(pid, "set_selection", {"element_ids": [eid]})
    store.execute(pid, "set_playhead", {"time": 3})
    store.execute(pid, "move_clip", {"start": 1.6}, 1, "agent")
    store = Store(store.root)
    assert store.context(pid)["selected"][0]["start"] == 1.6
    assert store.context(pid)["playhead"] == 3
    assert store.read(pid)["history"][-1]["actor"] == "agent"
    undone = store.execute(pid, "undo", {}, 2)
    assert undone["project"]["elements"][0]["start"] == 2
    assert undone["project"]["revision"] == 3
    store.execute(pid, "redo", {}, 3)
    store.execute(pid, "undo", {}, 4)
    branched = store.execute(pid, "set_property", {"element_id": eid, "property": "text", "value": "Manual refinement"}, 5)
    assert not branched["canRedo"]
    assert branched["project"]["elements"][0]["text"] == "Manual refinement"


def test_invalid_commands_and_concurrent_writes_are_atomic(fc):
    store, pid, eid = fc
    before = store.read(pid)
    for args in [{"start": -1}, {"start": float("nan")}, {"start": 14}]:
        with pytest.raises(EditorError): store.execute(pid, "move_clip", {"element_id": eid, **args}, 1)
    assert store.read(pid) == before
    def edit(value):
        try:
            Store(store.root).execute(pid, "set_property", {"element_id": eid, "property": "text", "value": value}, 1)
            return "saved"
        except EditorError as e:
            return e.code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(edit, ["One", "Two"])) == ["revision_conflict", "saved"]
    assert len(store.read(pid)["history"]) == 2


def test_proposal_exact_preview_atomic_undo_and_staleness(fc):
    store, pid, eid = fc
    store.execute(pid, "set_selection", {"element_ids": [eid]})
    s = store.execute(pid, "propose_changes", {"description": "Stronger, earlier headline", "commands": [
        {"name": "move_clip", "args": {"start": 1.6}},
        {"name": "apply_motion", "args": {"motion_id": "impact-rise", "duration": .5}},
        {"name": "add_text", "args": {"text": "CTA", "start": 10, "duration": 3}}]}, 1, "agent")
    proposal = s["proposals"][0]
    assert s["project"]["revision"] == 1
    applied = store.execute(pid, "apply_proposal", {"proposal_id": proposal["id"]}, 1, "agent")
    assert applied["project"]["elements"] == proposal["projectAfter"]["elements"]
    undone = store.execute(pid, "undo", {}, 2)
    assert len(undone["project"]["elements"]) == 1
    assert undone["project"]["elements"][0]["start"] == 2
    s = store.execute(pid, "propose_changes", {"commands": [{"name": "delete_clip", "args": {"element_id": eid}}]}, 3)
    proposal = s["proposals"][-1]
    store.execute(pid, "move_clip", {"element_id": eid, "start": 1}, 3)
    with pytest.raises(EditorError, match="nieaktualna"):
        store.execute(pid, "apply_proposal", {"proposal_id": proposal["id"]}, 4)


def test_split_preserves_animation_phase_and_trim_source(fc):
    store, pid, eid = fc
    s=store.execute(pid,"split_clip",{"element_id":eid,"time":3},1)
    left,right=s["project"]["elements"]
    assert left["duration"] == 1 and right["duration"] == 3
    assert right["sourceStart"] == 1 and right["motionOffset"] == 1
    store.execute(pid,"undo",{},2)
    assert store.read(pid)["project"]["elements"][0]["duration"] == 4


def test_asset_validation_and_composition_text_cannot_execute(fc):
    store,pid,eid=fc
    with pytest.raises(EditorError): import_asset(store,pid,b'<svg onload="alert(1)">',"evil.svg",expected_revision=1)
    with pytest.raises(Exception): import_asset(store,pid,b'not an image',"broken.png",expected_revision=1)
    assert not list((store.directory(pid)/"assets").iterdir())
    image=io.BytesIO();Image.new('RGB',(40,40),'red').save(image,format='PNG')
    s=import_asset(store,pid,image.getvalue(),'Product.png','product',1)
    asset=s['project']['assets'][0]
    assert asset['file'].startswith('assets/') and asset['kind']=='image'
    s=store.execute(pid,'set_property',{'element_id':eid,'property':'text','value':'</script><script>window.hacked=true</script>'},2)
    html=compile_project(s['project'])
    assert '</script><script>window.hacked' not in html
    assert '\\u003c/script' in html
    with pytest.raises(EditorError): store.execute(pid,'add_asset',{'asset':{**asset,'id':'other','file':'../../secret.png'}},3)


def test_storyboard_and_brand_format_are_shared_content(fc):
    store,pid,_=fc
    scenes=storyboard(15,'FORM')
    assert sum(s['duration'] for s in scenes) == 15
    s=store.execute(pid,'assemble_storyboard',{'scenes':scenes,'replace':True},1)
    assert len(s['project']['scenes']) == 6
    assert len(s['project']['elements']) == 12
    s=store.execute(pid,'set_brand',{'brand':{'font':'Georgia','colors':{'background':'#000000','text':'#ffffff','accent':'#ff0000'}}},2)
    assert all(e['style']['fontFamily']=='Georgia' for e in s['project']['elements'])
    old=s['project']['elements'][0]['x']
    s=store.execute(pid,'set_format',{'format':'16:9'},3)
    assert s['project']['canvas']['width'] == 1920
    assert s['project']['elements'][0]['x'] == old*1920/1080


def test_real_http_mcp_human_agent_undo(fc):
    store,pid,eid=fc
    srv,_=start_background(store)
    base=f'http://127.0.0.1:{srv.server_port}'
    def post(name,args):
        data=json.dumps({'name':name,'args':{'project_id':pid,**args}}).encode()
        req=Request(base+'/api/command',data,headers={'Content-Type':'application/json','X-Studio-Token':srv.token})
        with urlopen(req) as r:return json.load(r)
    try:
        post('set_selection',{'element_ids':[eid]})
        post('set_property',{'property':'text','value':'Human edit','expected_revision':1})
        proc=subprocess.Popen([sys.executable,str(REPO/'framecore.py'),'mcp','--root',str(store.root)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,cwd=REPO)
        def rpc(mid,method,params):
            proc.stdin.write(json.dumps({'jsonrpc':'2.0','id':mid,'method':method,'params':params})+'\n');proc.stdin.flush()
            return json.loads(proc.stdout.readline())['result']
        try:
            assert rpc(1,'initialize',{'protocolVersion':'2025-06-18'})['serverInfo']['name']=='tabasco-framecore'
            context=json.loads(rpc(2,'tools/call',{'name':'get_selection','arguments':{'project_id':pid}})['content'][0]['text'])
            assert context['selected'][0]['text']=='Human edit'
            result=rpc(3,'tools/call',{'name':'move_clip','arguments':{'project_id':pid,'start':1.6,'expected_revision':2}})
            assert not result['isError']
        finally:
            proc.stdin.close();proc.wait(timeout=10)
        with urlopen(base+'/api/project/'+pid) as r:
            shared=json.load(r)
        assert shared['project']['elements'][0]['start']==1.6
        assert shared['history'][-1]['actor']=='agent'
        result=post('undo',{'expected_revision':3})
        assert result['project']['elements'][0]['start']==2
        result=post('set_property',{'property':'x','value':120,'expected_revision':4})
        assert result['project']['elements'][0]['x']==120
        with pytest.raises(HTTPError) as failure:
            urlopen(Request(base+'/api/command',b'{}',headers={'Content-Type':'application/json'}))
        assert failure.value.code==403
        with pytest.raises(HTTPError) as conflict:
            post('move_clip',{'element_id':eid,'start':1,'expected_revision':1})
        assert conflict.value.code==409
    finally:
        srv.shutdown();srv.server_close()


def test_missing_provider_never_fakes_assets(fc):
    store,pid,_=fc
    api=API(store,RenderJobs(store))
    with pytest.raises(EditorError,match='Brak skonfigurowanego') as err:
        api.call('generate_image',{'project_id':pid,'prompt':'product photo'})
    assert err.value.code=='provider_unavailable'
    assert store.read(pid)['project']['assets']==[]


def test_job_status_is_visible_to_a_separate_transport_and_rejects_traversal(fc):
    store,pid,_=fc
    jobs=RenderJobs(store)
    from vstudio.locking import atomic_write
    job={'id':'render_test','project_id':pid,'revision':1,'status':'complete','progress':1,'url':'/exports/example'}
    atomic_write(jobs._path('render_test'),json.dumps(job))
    assert RenderJobs(Store(store.root)).get('render_test')==job
    with pytest.raises(EditorError): jobs.get('../state')


def test_keyframes_split_interpolation_format_and_rejected_writes(fc):
    store,pid,eid=fc
    api=API(store,RenderJobs(store))
    args={'project_id':pid,'expected_revision':1,'element_id':eid,
          'keyframes':[{'property':'x','time':0,'value':100},{'property':'x','time':4,'value':500}]}
    api.call('set_keyframes',args)
    s=api.call('split_clip',{'project_id':pid,'expected_revision':2,'element_id':eid,'time':3})
    left,right=s['project']['elements']
    assert left['keyframes'][-1]['value']==200
    assert right['keyframes'][0]['value']==200 and right['keyframes'][-1]['value']==500
    before=store.read(pid)
    for frames in [[{'property':'opacity','time':0,'value':2}], [{'property':'x','time':10,'value':0}],
                   [{'property':'x','time':0,'value':0},{'property':'x','time':0,'value':1}]]:
        with pytest.raises(EditorError): api.call('set_keyframes',{**args,'expected_revision':3,'keyframes':frames})
    assert store.read(pid)==before
    s=api.call('set_format',{'project_id':pid,'expected_revision':3,'format':'16:9'})
    assert s['project']['elements'][0]['keyframes'][-1]['value']==pytest.approx(200*1920/1080)
    s=api.call('duplicate_clip',{'project_id':pid,'expected_revision':4,'element_id':eid,'start':8})
    assert s['project']['elements'][-1]['keyframes']==s['project']['elements'][0]['keyframes']
    api.call('set_track',{'project_id':pid,'expected_revision':5,'track_id':'text','property':'locked','value':True})
    with pytest.raises(EditorError,match='zablokowana'):
        api.call('duplicate_clip',{'project_id':pid,'expected_revision':6,'element_id':eid,'start':9})


def test_library_templates_inspection_proposal_assets(fc):
    store,pid,eid=fc
    api=API(store,RenderJobs(store))
    assert len(api.call('list_motion')['components'])==28
    assert len(api.call('list_templates')['templates'])==12
    templates=[api.call('plan_storyboard',{'project_id':pid,'template_id':tid}) for tid in ('product','social','explainer','collaboration')]
    assert len({t['scenes'][0]['message'] for t in templates})==4
    s=api.call('propose_changes',{'project_id':pid,'expected_revision':1,'commands':[{'name':'add_icon','args':{'icon_id':'robot','start':0,'duration':3}}]})
    proposal=s['proposals'][-1]
    assert s['project']['assets']==[]
    s=api.call('apply_proposal',{'project_id':pid,'expected_revision':1,'proposal_id':proposal['id']})
    icon=s['project']['assets'][0]
    assert (store.directory(pid)/icon['file']).is_file() and icon['license']=='MIT'
    assert s['project']['elements']==proposal['projectAfter']['elements']
    s=api.call('set_property',{'project_id':pid,'expected_revision':2,'element_id':eid,'property':'x','value':-10})
    assert api.call('inspect_project',{'project_id':pid})['issues'][0]['code']=='outside_canvas'
    assert 'capture_frame' in api.call('get_editing_guide')['instructions']
    with pytest.raises(EditorError):api.call('add_icon',{'project_id':pid,'expected_revision':3,'icon_id':'../../etc/passwd'})
    s=api.call('apply_template',{'project_id':pid,'expected_revision':3,'template_id':'collaboration','replace':True})
    assert len(s['project']['scenes'])==6
    assert s['project']['scenes'][-1]['message']=='Stwórzmy film razem.'


def test_audio_settings_trim_and_split_are_atomic(fc):
    import wave
    store,pid,_=fc
    data=io.BytesIO()
    with wave.open(data,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0\0'*8000*6)
    s=import_asset(store,pid,data.getvalue(),'sound.wav',expected_revision=1)
    s=store.execute(pid,'add_audio',{'assetId':s['project']['assets'][0]['id'],'duration':6},2)
    eid=s['project']['elements'][-1]['id']
    s=store.execute(pid,'set_audio',{'element_id':eid,'audio':{'gain':.4,'fadeIn':1,'fadeOut':2}},3)
    before=store.read(pid)
    with pytest.raises(EditorError):store.execute(pid,'set_audio',{'element_id':eid,'audio':{'fadeIn':7}},4)
    assert store.read(pid)==before
    s=store.execute(pid,'split_clip',{'element_id':eid,'time':3},4)
    audio=[e for e in s['project']['elements'] if e['type']=='audio']
    assert audio[0]['audio']=={'gain':.4,'fadeIn':1,'fadeOut':0}
    assert audio[1]['audio']=={'gain':.4,'fadeIn':0,'fadeOut':2}
