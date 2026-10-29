"""Prepare a reproducible Xcode input tree on a macOS runner (Python 3.13)."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent
URL = 'https://github.com/beeware/Python-Apple-support/releases/download/3.13-b15/Python-3.13-iOS-support.b15.tar.gz'
DIGEST = '80175765a31babe43b0910395cf86ba4e8412adf1902b069d55b74d523ecc5d1'


def prepare_frontend(resources):
    shutil.copytree(ROOT.parent/'android/app/src/main/assets/frontend', resources/'frontend', dirs_exist_ok=True)
    shutil.copytree(ROOT/'frontend', resources/'frontend', dirs_exist_ok=True)
    index = resources/'frontend/index.html'
    html = index.read_text(encoding='utf-8')
    html = html.replace('</head>', '<link rel="stylesheet" href="ios.css"></head>')
    html = html.replace('</body>', '<script src="ios-ui.js"></script></body>')
    index.write_text(html, encoding='utf-8')


def main():
    if sys.platform != 'darwin' or sys.version_info[:2] != (3, 13):
        raise SystemExit('Run on macOS with Python 3.13. Windows can edit sources, but cannot build iOS.')
    support = ROOT/'Support'
    support.mkdir(exist_ok=True)
    archive = support/'Python-iOS.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != DIGEST:
        raise SystemExit('Python support package checksum mismatch')
    if not (support/'Python.xcframework').exists():
        with tarfile.open(archive) as package:
            package.extractall(support, filter='data')
    resources = ROOT/'Resources'
    resources.mkdir(exist_ok=True)
    # Only source code and translations enter the app; never local credentials.
    core = resources/'core'
    core.mkdir(exist_ok=True)
    for source in (ROOT.parent/'core').rglob('*'):
        if source.is_file() and (source.suffix == '.py' or source.parent.name == 'locales' and source.suffix == '.json') and '__pycache__' not in source.parts:
            target = core/source.relative_to(ROOT.parent/'core')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    prepare_frontend(resources)
    env = dict(os.environ, AIOHTTP_NO_EXTENSIONS='1', MULTIDICT_NO_EXTENSIONS='1',
               YARL_NO_EXTENSIONS='1', FROZENLIST_NO_EXTENSIONS='1', PROPCACHE_NO_EXTENSIONS='1')
    wheels = support/'wheels'
    wheels.mkdir(exist_ok=True)
    subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-cache-dir',
                    '--no-binary', 'aiohttp,multidict,yarl,frozenlist,propcache',
                    '--wheel-dir', str(wheels), '-r', str(ROOT/'requirements.txt')], env=env, check=True)
    if any(not p.name.endswith('-none-any.whl') for p in wheels.glob('*.whl')):
        raise SystemExit('A native desktop wheel was produced. Do not bundle it for iOS.')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--find-links', str(wheels),
                    '--no-compile', '--upgrade', '--target', str(resources/'vendor'), '-r', str(ROOT/'requirements.txt')], check=True)
    if any(p.suffix in {'.so', '.dylib', '.pyd'} for p in (resources/'vendor').rglob('*')):
        raise SystemExit('Unexpected native extension in vendor packages')
    # Render the existing crescent motif as an opaque iOS icon.
    from PIL import Image, ImageDraw
    icon = Image.new('RGB', (1024,1024), '#21182f')
    draw = ImageDraw.Draw(icon)
    draw.ellipse((210,180,814,820), fill='#cbb0f5')
    draw.ellipse((415,95,965,665), fill='#21182f')
    draw.polygon([(742,260),(765,318),(826,338),(765,359),(742,418),(721,359),(663,338),(721,318)], fill='#eee4fa')
    assets = resources/'Assets.xcassets'
    appicon = assets/'AppIcon.appiconset'
    appicon.mkdir(parents=True, exist_ok=True)
    icon.save(appicon/'Icon.png')
    (appicon/'Contents.json').write_text(json.dumps({'images':[{'idiom':'universal','platform':'ios','size':'1024x1024','filename':'Icon.png'}],'info':{'version':1,'author':'xcode'}}))
    (assets/'Contents.json').write_text('{"info":{"version":1,"author":"xcode"}}')
    colors = assets/'LaunchBackground.colorset'
    colors.mkdir(exist_ok=True)
    (colors/'Contents.json').write_text(json.dumps({'colors':[{'idiom':'universal','color':{'color-space':'srgb','components':{'red':'0.047','green':'0.043','blue':'0.063','alpha':'1.0'}}}], 'info':{'version':1,'author':'xcode'}}))
    print('Shared frontend, embedded core, pure Python dependencies and icon are ready.')


if __name__ == '__main__':
    main()
