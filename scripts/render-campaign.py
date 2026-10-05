"""Create, validate and export the editable campaign through FrameCore's API."""
import json
from pathlib import Path
import shutil
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from framecore.campaign import create_campaign
from framecore.store import Store
from framecore.api import API
from framecore.render import RenderJobs

root=Path(__file__).resolve().parents[1]
store=Store()
state=store.read(sys.argv[1]) if len(sys.argv)>1 else create_campaign(store)
pid=state['project']['id']
api=API(store,RenderJobs(store))
qa=api.call('inspect_project',{'project_id':pid})
output=root/'output'/'campaign';output.mkdir(parents=True,exist_ok=True)
(output/'project.json').write_text(json.dumps(state['project'],ensure_ascii=False,indent=2),encoding='utf-8')
(output/'inspection.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'project_id':pid,'qa':qa}),flush=True)
job=api.call('export',{'project_id':pid,'expected_revision':state['project']['revision']})
while job['status'] not in ('failed','complete'):
    time.sleep(3)
    job=api.call('get_job',{'job_id':job['id']})
    print(json.dumps(job),flush=True)
(output/'result.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
if job['status']!='complete':raise RuntimeError(job['error'])
shutil.copy2(store.directory(pid)/'exports'/job['id']/'framecore.mp4',root/'assets'/'framecore-agent-campaign.mp4')
print('Saved assets/framecore-agent-campaign.mp4',flush=True)
