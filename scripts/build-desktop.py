"""Build on the target OS; never cross-compile a misleading installer."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def binary(name):
    supplied=os.environ.get('FRAMECORE_'+name.upper())
    if supplied:return Path(supplied).resolve()
    if sys.platform=='win32':
        candidates=list((Path(os.environ.get('ChocolateyInstall','C:/ProgramData/chocolatey'))/'lib/ffmpeg').rglob(name+'.exe'))
        if candidates:return max(candidates,key=lambda p:p.stat().st_size).resolve()
    found=shutil.which(name)
    if not found:raise RuntimeError(f'Brak {name} na maszynie budującej')
    return Path(found).resolve()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--skip-build',action='store_true')
    parser.add_argument('--system-browser-for-smoke',action='store_true',help='Linux development smoke only; never used for Windows/macOS releases')
    args=parser.parse_args()
    generated=ROOT/'packaging/generated';generated.mkdir(parents=True,exist_ok=True)
    image=Image.open(ROOT/'assets/framecore-logo-mark.png').convert('RGBA')
    square=Image.new('RGBA',(1024,1024),'#191c1e');image.thumbnail((750,750));square.alpha_composite(image,((1024-image.width)//2,(1024-image.height)//2))
    square.save(generated/'icon.ico',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    square.save(generated/'icon.icns')
    native=generated/'native';native.mkdir(exist_ok=True);notices=native/'licenses';notices.mkdir(exist_ok=True)
    manifest={'platform':sys.platform,'python':sys.version,'tools':{},'dependencies':{}}
    for name in ['ffmpeg','ffprobe']:
        source=binary(name);target=native/(name+'.exe' if sys.platform=='win32' else name);shutil.copy2(source,target)
        version=subprocess.run([str(source),'-version'],check=True,capture_output=True,text=True).stdout
        manifest['tools'][name]={'source':str(source),'version':version,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    license_text=subprocess.run([str(binary('ffmpeg')),'-L'],check=True,capture_output=True,text=True)
    (notices/'FFmpeg-license.txt').write_text(license_text.stdout+license_text.stderr,encoding='utf-8')
    # Preserve available upstream texts, including the PyInstaller bootloader exception.
    for package in ['pywebview','pyinstaller','playwright','numpy','Pillow','certifi','pythonnet','clr-loader','bottle','proxy-tools','pyobjc-core','pyobjc-framework-Cocoa','pyobjc-framework-WebKit','pyobjc-framework-Quartz']:
        try:dist=importlib.metadata.distribution(package)
        except importlib.metadata.PackageNotFoundError:continue
        manifest['dependencies'][package]=dist.version
        for file in dist.files or []:
            if any(word in file.name.lower() for word in ['license','copying','copyright']):
                path=dist.locate_file(file)
                if path.is_file() and path.stat().st_size<2_000_000:
                    shutil.copy2(path,notices/(package+'-'+file.name))
    (native/'tool-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    browsers=Path(os.environ.get('PLAYWRIGHT_BROWSERS_PATH',generated/'browsers')).resolve()
    if args.system_browser_for_smoke:
        if sys.platform!='linux':raise RuntimeError('System browser substitute is only for the Linux development smoke')
        import playwright
        metadata=json.loads((Path(playwright.__file__).parent/'driver/package/browsers.json').read_text())
        versions={b['name']:b['revision'] for b in metadata['browsers']}
        for folder,part,executable in [('chromium-'+versions['chromium'],'chrome-linux64','chrome'),
                                      ('chromium_headless_shell-'+versions['chromium-headless-shell'],'chrome-headless-shell-linux64','chrome-headless-shell')]:
            target=browsers/folder/part
            if not target.exists():shutil.copytree('/usr/lib/chromium',target,symlinks=True)
            (target/executable).unlink(missing_ok=True)
            shutil.copy2(target/'chromium',target/executable)
        manifest['development_browser']='System Chromium copied for Linux smoke; not a release browser'
        (native/'tool-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    if not browsers.is_dir() or not any(browsers.glob('chromium*')):raise RuntimeError('Najpierw pobierz Chromium do PLAYWRIGHT_BROWSERS_PATH')
    os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(browsers);os.environ['FRAMECORE_NATIVE_DIR']=str(native)
    if not args.skip_build:subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean',str(ROOT/'packaging/framecore.spec')],cwd=ROOT,check=True)


if __name__=='__main__':main()
