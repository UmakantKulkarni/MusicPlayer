# Third-party components

The executable bundles Python and libraries. Their license notices are included in
`third_party/` in this repository; keep those notices with redistributions. Locally
generated distribution bundles also contain `THIRD_PARTY_LICENSES.zip`.

- CPython / Tcl / Tk: Python Software Foundation and Tcl/Tk licenses.
- pygame-ce / SDL_mixer and their codec libraries: pygame-ce is LGPL-2.1-or-later; bundled SDL libraries and codecs have their own licenses. See the included pygame-ce license directory.
- Mutagen: GPL-2.0-or-later. Its inclusion means a distributed combined application must comply with applicable GPL terms. This project is distributed under GPL-2.0-or-later, with full application source included in the distribution.
- PyInstaller: GPL-2.0-or-later with its bootloader exception, which permits packaging applications. See the bundled notice.

The application dynamically loads its bundled SDL/pygame libraries. Source code
for dependencies is available at https://github.com/pygame-community/pygame-ce,
https://github.com/libsdl-org/SDL, https://github.com/libsdl-org/SDL_mixer,
https://github.com/quodlibet/mutagen, https://github.com/pyinstaller/pyinstaller,
and https://github.com/python/cpython. Refer to their exact bundled version notices
for additional codec source locations. Distributors should retain notices and meet
applicable source availability obligations for the versions they redistribute.
