"""Resources and durable user data for the frozen desktop distribution."""
import os
import sys
from pathlib import Path

APP_NAME = 'FrameCore Studio'


def data_directory(platform=None):
    platform = platform or sys.platform
    if platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    return base / APP_NAME


def configure():
    """Only packaged apps use bundled tools; source installations keep their PATH."""
    if not getattr(sys, 'frozen', False):
        return
    resources = Path(sys._MEIPASS)
    native = resources / 'native'
    os.environ['PATH'] = str(native) + os.pathsep + os.environ.get('PATH', '')
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(resources / 'browsers')
    os.environ['FRAMECORE_PORTABLE_MEDIA'] = '1'
    certificate=resources/'certificates/cacert.pem'
    if certificate.is_file():os.environ.setdefault('SSL_CERT_FILE',str(certificate))
    os.environ['FRAMECORE_ENGINE'] = str(Path(sys.executable).with_name(
        'FrameCoreEngine.exe' if sys.platform == 'win32' else 'FrameCoreEngine'))
    # Independent app processes share project locks, but never installation files.
    os.environ['PYTHONUTF8'] = '1'


def renderer_command(arguments, log_path):
    if getattr(sys, 'frozen', False):
        return [os.environ['FRAMECORE_ENGINE'], '--render-worker', str(log_path), *arguments]
    script = Path(__file__).resolve().parents[1] / 'vstudio/renderers/html_to_video.py'
    return [sys.executable, str(script), *arguments]


def process_options():
    # Console workers must not flash terminal windows over the installed GUI.
    return {'creationflags': 0x08000000} if sys.platform == 'win32' and getattr(sys, 'frozen', False) else {}


def mcp_config(root):
    if getattr(sys, 'frozen', False):
        return {'command': os.environ['FRAMECORE_ENGINE'], 'args': ['--mcp', '--root', str(root.resolve())]}
    repo = Path(__file__).resolve().parents[1]
    return {'command': sys.executable, 'args': [str(repo / 'framecore.py'), 'mcp', '--root', str(root.resolve())], 'cwd': str(repo)}
