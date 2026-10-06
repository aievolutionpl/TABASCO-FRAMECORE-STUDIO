# Two executables share one Python runtime, resources and bundled media tools.
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, copy_metadata
import certifi

root = Path(SPECPATH).parent
version = '0.3.3'
native = Path(os.environ['FRAMECORE_NATIVE_DIR'])
browsers = Path(os.environ['PLAYWRIGHT_BROWSERS_PATH'])
datas = [(str(root/'framecore/static'),'framecore/static'),
         (str(root/'assets'),'assets'), (str(root/'examples'),'examples'),
         (str(root/'licenses'),'licenses'), (str(root/'LICENSE'),'.'),
         (str(root/'THIRD_PARTY_NOTICES.md'),'.'),
         (str(root/'packaging/TOOL_NOTICES.md'),'desktop-licenses'),
         (str(native/'tool-manifest.json'),'desktop-licenses'),
         (certifi.where(),'certificates')]
datas += collect_data_files('webview') + copy_metadata('pywebview') + copy_metadata('playwright')
datas += [(str(file),'desktop-licenses') for file in (native/'licenses').glob('*')]
hidden = ['webview.platforms.edgechromium'] if sys.platform=='win32' else ['webview.platforms.cocoa'] if sys.platform=='darwin' else []
a = Analysis([str(root/'desktop_app.py'),str(root/'desktop_engine.py')], pathex=[str(root)],
             binaries=[(str(native/('ffmpeg.exe' if sys.platform=='win32' else 'ffmpeg')),'native'),
                       (str(native/('ffprobe.exe' if sys.platform=='win32' else 'ffprobe')),'native')],
             datas=datas, hiddenimports=hidden, excludes=['pytest','tkinter'])
pyz = PYZ(a.pure)
hooks = [item for item in a.scripts if item[0] not in {'desktop_app','desktop_engine'}]
entry = {item[0]:item for item in a.scripts if item[0] in {'desktop_app','desktop_engine'}}
icon = str(root/'packaging/generated/icon.ico') if sys.platform=='win32' else str(root/'packaging/generated/icon.icns') if sys.platform=='darwin' else None
gui = EXE(pyz,hooks+[entry['desktop_app']],[],exclude_binaries=True,name='FrameCoreStudio',console=sys.platform not in {'win32','darwin'},icon=icon)
engine = EXE(pyz,hooks+[entry['desktop_engine']],[],exclude_binaries=True,name='FrameCoreEngine',console=True)
coll = COLLECT(gui,engine,a.binaries,a.datas,name='FrameCoreStudio')
if sys.platform=='darwin':
    app = BUNDLE(coll,name='MotionDuo Studio.app',icon=icon,bundle_identifier='pl.aievolution.framecore.studio',
        info_plist={'CFBundleShortVersionString':version,'CFBundleVersion':'1','NSHighResolutionCapable':True,
                    'NSLocalNetworkUsageDescription':'Studio łączy lokalny edytor z materiałami i silnikiem eksportu na tym komputerze.'})
