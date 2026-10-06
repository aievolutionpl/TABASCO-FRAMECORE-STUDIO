"""Assemble a static GitHub Pages site with only the assets it uses."""
import argparse
from pathlib import Path
import shutil
import subprocess
ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'dist/site');args=parser.parse_args()
    out=args.out.resolve()
    if out==ROOT or ROOT.is_relative_to(out) or out==ROOT/'site':raise ValueError('Nie można nadpisać katalogu źródłowego')
    out.mkdir(parents=True,exist_ok=True)
    for file in (ROOT/'site').iterdir():
        if file.is_file():shutil.copy2(file,out/file.name)
    assets=out/'assets';assets.mkdir(exist_ok=True)
    for source,target in [('assets/motionduo-mark.png','mark.png'),('assets/motionduo-editor.png','editor.png'),
                          ('assets/framecore-visual-lesson-demo.mp4','lesson.mp4'),('framecore/static/library/fonts/manrope.ttf','manrope.ttf'),
                          ('licenses/fonts/manrope-OFL.txt','Manrope-OFL.txt')]:shutil.copy2(ROOT/source,assets/target)
    subprocess.run(['ffmpeg','-y','-v','error','-ss','1.3','-i',str(assets/'lesson.mp4'),'-frames:v','1',str(assets/'lesson-poster.jpg')],check=True)
    (out/'.nojekyll').touch()
    print(out)


if __name__=='__main__':main()
