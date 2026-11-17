# Validation of the initial distribution

The development host is Linux (Debian 13). The Windows executable is a genuine
64-bit Windows PE built with Windows CPython 3.12.7 under Wine 10, using
PyInstaller 6.11.1, pygame-ce 2.5.3, and Mutagen 1.47.0.

- 13 unit/integration tests pass on Linux Python 3.12.14 with an Xvfb display.
- The same 13 tests pass using Windows Python under Wine, including the Tk GUI.
- Windows SDL decoding/playback tested with generated MP3, OGG, FLAC, and WAV files.
  MP3, OGG, and FLAC seeking also verified. Audio output uses a dummy device.
- The final packaged EXE's self-test verifies the actual bundled Tk UI, audio-file
  import, SQLite playlists, M3U roundtrip, pause/resume, playback completion,
  application shutdown, and database persistence after reopening.
- The Windows Tk interface was visually checked at 1120 × 740 under Wine.
  The screenshot contains demo metadata, not supplied music.

No native Windows computer or physical audio device was available in this task.
Speaker output, Windows SmartScreen reputation, company endpoint policy, and
native Windows behavior have not been verified here. The repository includes a
GitHub Actions Windows runner workflow for native automated validation on push.
That workflow has not been run in this task. The EXE is unsigned.

These validation checks were performed before repository publication. Refer to
the GitHub commit history and Actions runs for subsequent upload and native CI status.
