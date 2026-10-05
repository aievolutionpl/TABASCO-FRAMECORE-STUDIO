import json
import shutil
import pytest
from playwright.sync_api import sync_playwright
from framecore.api import API
from framecore.model import EditorError
from framecore.store import Store
from framecore.render import RenderJobs
from framecore.server import start_background


def setup(tmp_path):
    store=Store(tmp_path/'projects');p=store.create('Ruch','16:9',2)['project'];pid=p['id']
    raw=store._load(pid);raw['project']['canvas'].update(width=320,height=180);store._save(raw)
    store.execute(pid,'add_text',{'text':'Ruch','x':20,'y':30,'width':180,'height':100,'duration':2,'style':{'fontSize':40}},0)
    store.execute(pid,'add_scene',{'name':'Otwarcie','start':0,'duration':2},1)
    eid=store.read(pid)['project']['elements'][0]['id']
    store.execute(pid,'set_keyframes',{'element_id':eid,'keyframes':[{'property':'x','time':0,'value':20},{'property':'x','time':1.9,'value':100}]},2)
    return store,API(store,RenderJobs(store)),pid,eid


def test_scene_time_addresses_and_invalid_values(tmp_path):
    store,api,pid,_=setup(tmp_path)
    from framecore.motion_evidence import resolve_time
    p=store.read(pid)['project'];fps=p['canvas']['fps']
    assert resolve_time(p,'Otwarcie@50%')==1
    assert resolve_time(p,'Otwarcie@end')==pytest.approx(2-1/fps)
    assert resolve_time(p,'30f')==1
    assert resolve_time(p,'1000ms')==1
    assert resolve_time(p,'0:01')==1
    for value in ['Otwarcie@101%','0:99','-2f','nan s','nieznana@1s',True,'3000f','../../x@1s']:
        with pytest.raises(EditorError):resolve_time(p,value)
    assert api.call('resolve_frame_time',{'project_id':pid,'spec':'Otwarcie@50%'})['time']==1


@pytest.mark.browser
def test_real_onion_snapshot_difference_and_mcp_images(tmp_path):
    store,api,pid,eid=setup(tmp_path)
    args={'project_id':pid,'expected_revision':3,'start':'Otwarcie@0s','end':'Otwarcie@end','count':6}
    r=api.call('create_motion_strip',args);again=api.call('create_motion_strip',args)
    from PIL import Image
    import numpy as np
    out=store.directory(pid)/'reviews'/r['id']
    onion=np.asarray(Image.open(out/'onion.png'))
    assert onion.shape[:2]==(180,320)
    assert not np.array_equal(onion,np.asarray(Image.open(out/r['frames'][-1]['file'])))
    same=api.call('compare_reviews',{'project_id':pid,'baseline_id':r['id'],'review_id':again['id']})
    assert same['matched'] and all(f['changedRatio']==0 for f in same['frames'])
    store.execute(pid,'set_property',{'element_id':eid,'property':'text','value':'Zmiana'},3)
    new=api.call('create_motion_strip',{**args,'expected_revision':4})
    diff=api.call('compare_reviews',{'project_id':pid,'baseline_id':r['id'],'review_id':new['id']})
    assert not diff['matched'] and any(f['changedRatio']>0 for f in diff['frames'])
    other=api.call('create_review',{'project_id':pid,'expected_revision':4,'times':[.5]})
    with pytest.raises(EditorError,match='czasów'):
        api.call('compare_reviews',{'project_id':pid,'baseline_id':r['id'],'review_id':other['id']})
    from framecore.mcp import FrameCoreMCP
    mcp=FrameCoreMCP(api);mcp.initialized=True
    result=mcp._dispatch('tools/call',{'name':'get_review','arguments':{'project_id':pid,'review_id':new['id']}})
    assert [x['mimeType'] for x in result['content'] if x['type']=='image']==['image/jpeg','image/png']
    assert len(api.call('list_reviews',{'project_id':pid})['reviews'])==4


@pytest.mark.browser
def test_motion_lab_dashboard_scene_strip(tmp_path):
    store,_,pid,_=setup(tmp_path);srv,_=start_background(store);errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(**({'executable_path':shutil.which('chromium')} if shutil.which('chromium') else {}))
            page=browser.new_page(viewport={'width':1512,'height':982});page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{srv.server_port}');page.wait_for_function('document.querySelector("#player").ready')
            page.click('[data-tab="Production"]');page.get_by_text('Laboratorium ruchu · fframes',exact=True).click()
            scene=store.read(pid)['project']['scenes'][0]['id'];page.select_option('#motionScene',scene);page.fill('#motionCount','6')
            page.click('[data-production-action="strip"]');page.locator('img[alt="Tor ruchu z nałożonych klatek"]').wait_for(timeout=30000)
            assert page.locator('img[alt="Tor ruchu z nałożonych klatek"]').evaluate('el=>el.complete && el.naturalWidth===320')
            assert not errors
            browser.close()
    finally:srv.shutdown();srv.server_close()
