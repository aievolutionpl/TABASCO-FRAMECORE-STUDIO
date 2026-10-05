"""Opt-in live provider smoke check. Never prints credentials or the session token."""
import json
import re
import time
import argparse
from pathlib import Path
from urllib.request import urlopen, Request

parser=argparse.ArgumentParser(description='Opt-in provider check; a project is sent only with --project.')
parser.add_argument('--project',help='Project id explicitly approved for sending to the configured provider')
args=parser.parse_args()
base='http://127.0.0.1:8877'
page=urlopen(base).read().decode()
token=re.search(r"window.STUDIO_TOKEN='([^']+)'",page).group(1)
def call(path,body=None):
    request=Request(base+path,data=json.dumps(body).encode() if body is not None else None,
                    headers={'Content-Type':'application/json','Origin':base,'X-Studio-Token':token})
    with urlopen(request,timeout=100) as response:return json.load(response)
try:
    test=call('/api/assistant/test',{})
    print(json.dumps(test),flush=True)
    if not args.project: raise SystemExit(0)
    job=call('/api/assistant/run',{'project_id':args.project,'prompt':'Wykonaj wyłącznie get_project i get_selection. Podaj długość filmu, liczbę scen i bieżącą rewizję. Nie zmieniaj projektu i nie eksportuj.'})
    while job['status']=='running':
        time.sleep(2)
        job=call('/api/assistant/job/'+job['id'])
    Path('output/qa-live-agent.json').write_text(json.dumps({'connection':test,'job':job},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(job,ensure_ascii=True),flush=True)
except Exception as exc:
    if hasattr(exc,'read'):
        print(exc.read().decode(),flush=True)
    else: print(type(exc).__name__,flush=True)
    raise SystemExit(1)
