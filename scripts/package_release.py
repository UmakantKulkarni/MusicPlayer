"""Create a redistributable bundle with source and third-party license notices."""
from pathlib import Path
import hashlib
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'release'
OUT.mkdir(exist_ok=True)
exe = ROOT / 'dist' / 'MusicPlayer.exe'
if not exe.is_file():
    raise SystemExit('Build dist/MusicPlayer.exe first on Windows.')
source = OUT / 'MusicPlayer-source.zip'
with zipfile.ZipFile(source, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(ROOT.rglob('*')):
        relative = path.relative_to(ROOT)
        if any(part in {'.git', '.venv', '__pycache__', 'build', 'dist', 'release', '.pytest_cache'} for part in relative.parts):
            continue
        roots = {'music_player', 'tests', 'scripts', '.github', 'docs', 'third_party'}
        files = {'main.py', 'README.md', 'VALIDATION.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md',
                 'requirements.txt', 'requirements-build.txt', 'MusicPlayer.spec', '.gitignore'}
        if path.is_file() and (relative.parts[0] in roots or relative.as_posix() in files):
            archive.write(path, relative.as_posix())
notices = OUT / 'THIRD_PARTY_LICENSES.zip'
with zipfile.ZipFile(notices, 'w', zipfile.ZIP_DEFLATED) as archive:
    runtime = Path(sys.base_prefix)
    for path in sorted(runtime.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(runtime)
        if (any(part.endswith('.dist-info') for part in relative.parts) and 'licenses' in relative.parts) or path.name.lower().startswith(('license', 'copying', 'copyright')):
            archive.write(path, relative.as_posix())
    for path in sorted((ROOT / 'third_party').rglob('*')):
        if path.is_file():
            archive.write(path, path.relative_to(ROOT).as_posix())
    archive.write(ROOT / 'THIRD_PARTY_NOTICES.md', 'THIRD_PARTY_NOTICES.md')
checksums = OUT / 'SHA256SUMS.txt'
checksums.write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in (exe, source, notices)), encoding='utf-8')
bundle = OUT / 'MusicPlayer-Windows-x64.zip'
with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in (exe, source, notices, checksums, ROOT / 'README.md', ROOT / 'LICENSE', ROOT / 'THIRD_PARTY_NOTICES.md'):
        archive.write(path, 'MusicPlayer/' + path.name)
    for path in (ROOT / 'VALIDATION.md', ROOT / 'docs' / 'screenshot.png'):
        if path.is_file():
            archive.write(path, 'MusicPlayer/' + path.name)
print(f'Bundle: {bundle}')
