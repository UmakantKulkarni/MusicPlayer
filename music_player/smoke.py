"""Packaged-app verification, invoked explicitly by maintainers with --self-test."""
import json
import os
import tempfile
import time
import wave
from pathlib import Path


def run(report_path):
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    import tkinter as tk
    from .app import App
    from .library import Library
    from .playback import Player
    report = {"ok": False, "checks": []}
    root = app = None
    try:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            song = path / "Demo track.wav"
            with wave.open(str(song), "wb") as audio:
                audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                audio.writeframes(b"\0\0" * 8000)
            root = tk.Tk()
            library = Library(path / "library.sqlite3")
            app = App(root, library=library, player=Player())
            app.import_paths([song])
            root.update()
            assert len(app.rows) == 1 and app.rows[0]["duration"] == 1
            report["checks"].append("Tk interface and audio-file import")
            playlist = library.create_playlist("Demo playlist")
            library.add_to_playlist(playlist, [app.rows[0]["id"]])
            library.rename_playlist(playlist, "Saved playlist")
            library.export_m3u(path / "mix.m3u8", playlist)
            ids, errors = library.import_m3u(path / "mix.m3u8")
            assert len(ids) == 1 and not errors
            report["checks"].append("SQLite playlists and M3U roundtrip")
            app.play_selected()
            assert app.player.backend.get_busy()
            app.toggle_pause()
            assert app.player.state == "paused"
            app.toggle_pause()
            deadline = time.monotonic() + 5
            while app.player.state == "playing" and time.monotonic() < deadline:
                root.update()
                time.sleep(0.02)
                app.player.poll()
            assert app.player.state == "stopped"
            report["checks"].append("Bundled SDL playback, pause/resume and completion (dummy audio output)")
            app.close()
            app = root = None
            reopened = Library(path / "library.sqlite3")
            assert reopened.playlists()[0]["name"] == "Saved playlist"
            reopened.close()
            report["checks"].append("Database persistence after application closes")
        report["ok"] = True
    except Exception as exc:
        report["ok"] = False
        import traceback
        report["error"] = str(exc)
        report["traceback"] = traceback.format_exc()
    finally:
        if app is not None:
            app.close()
        elif root is not None:
            root.destroy()
        Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1
