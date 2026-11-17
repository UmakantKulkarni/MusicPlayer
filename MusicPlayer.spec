# Build on Windows with Python 3.12 x64. All dependencies are bundled.
from PyInstaller.utils.hooks import collect_all
pygame_data, pygame_binaries, pygame_hidden = collect_all('pygame')
a = Analysis(['main.py'], pathex=[], binaries=pygame_binaries,
             datas=pygame_data, hiddenimports=pygame_hidden + ['mutagen.mp3', 'mutagen.flac', 'mutagen.oggvorbis', 'mutagen.wave'],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='MusicPlayer',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
