from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from framecore.desktop_runtime import data_directory, renderer_command, mcp_config, configure
from framecore.model import EditorError
from framecore.portable_media import for_export
from framecore.server import import_asset
from framecore.store import Store


def test_desktop_data_and_frozen_workers(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'windows'));monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path/'linux'))
    monkeypatch.setattr(Path,'home',lambda:tmp_path/'home')
    assert data_directory('win32')==tmp_path/'windows/FrameCore Studio'
    assert data_directory('darwin')==tmp_path/'home/Library/Application Support/FrameCore Studio'
    assert data_directory('linux')==tmp_path/'linux/FrameCore Studio'
    monkeypatch.setattr(sys,'frozen',True,raising=False);monkeypatch.setattr(sys,'_MEIPASS',str(tmp_path/'resources'),raising=False)
    for key in ['PATH','PLAYWRIGHT_BROWSERS_PATH','FRAMECORE_ENGINE','FRAMECORE_PORTABLE_MEDIA','PYTHONUTF8']:
        monkeypatch.setenv(key,os.environ.get(key,''))
    configure();engine=os.environ['FRAMECORE_ENGINE']
    assert renderer_command(['film.html'],tmp_path/'render.log')==[engine,'--render-worker',str(tmp_path/'render.log'),'film.html']
    assert mcp_config(tmp_path)['args']==['--mcp','--root',str(tmp_path)]
    expected=tmp_path/('Resources/browsers' if sys.platform=='darwin' else 'resources/browsers')
    assert os.environ['PLAYWRIGHT_BROWSERS_PATH']==str(expected)
    assert os.environ['FRAMECORE_PORTABLE_MEDIA']=='1'


def test_portable_video_preserves_originals_and_reuses_content_cache(tmp_path,monkeypatch):
    source=tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=red:s=160x90:r=6:d=1',
                    '-c:v','libx264','-pix_fmt','yuv420p',str(source)],check=True)
    store=Store(tmp_path/'projects');p=store.create(duration=1)['project'];pid=p['id']
    state=import_asset(store,pid,source.read_bytes(),source.name);asset=state['project']['assets'][0]
    state=store.execute(pid,'add_video',{'assetId':asset['id'],'start':0,'duration':1},state['project']['revision'])
    p=state['project'];root=store.directory(pid);original=(root/asset['file']).read_bytes();before=deepcopy(store.read(pid))
    monkeypatch.setenv('FRAMECORE_PORTABLE_MEDIA','1')
    render_project=for_export(p,root);file=root/render_project['assets'][0]['file'];stat=file.stat()
    info=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',str(file)],capture_output=True,text=True,check=True).stdout)
    assert info['streams'][0]['codec_name']=='vp9'
    assert store.read(pid)==before and (root/asset['file']).read_bytes()==original
    assert render_project['elements']==p['elements'] and render_project['revision']==p['revision']
    assert for_export(p,root)==render_project and file.stat().st_mtime_ns==stat.st_mtime_ns
    changed=deepcopy(p);changed['assets'][0]['file']='assets/../../source.mp4'
    with pytest.raises(EditorError):for_export(changed,root)
    monkeypatch.delenv('FRAMECORE_PORTABLE_MEDIA');assert for_export(p,root)==p
