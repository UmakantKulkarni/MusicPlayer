"""Real SDL decoding, playback lifecycle, and Tk interaction smoke checks."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from music_player.library import Library
from music_player.playback import Player
from tests.test_library import make_wave


class AudioIntegrationTests(unittest.TestCase):
    def test_real_audio_backend(self):
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "tone.wav"
            make_wave(filename)
            library = Library(":memory:")
            library.add_track(filename)
            player = Player()
            try:
                player.play_queue(library.tracks())
                self.assertTrue(pygame.mixer.music.get_busy())
                player.toggle_pause()
                self.assertEqual(player.state, "paused")
                player.toggle_pause()
                deadline = time.monotonic() + 4
                while player.state == "playing" and time.monotonic() < deadline:
                    time.sleep(0.02)
                    player.poll()
                self.assertEqual(player.state, "stopped")
            finally:
                player.stop()
                pygame.mixer.quit()
                library.close()


class GuiIntegrationTests(unittest.TestCase):
    def test_import_select_play_search_and_reorder(self):
        import tkinter as tk
        from unittest.mock import Mock
        from music_player.app import App
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("A graphical display is required")
        with tempfile.TemporaryDirectory() as directory:
            db = Library(Path(directory) / "db.sqlite3")
            player = Player(Mock())
            app = App(root, library=db, player=player)
            try:
                filename = Path(directory) / "Song.wav"
                make_wave(filename)
                app.import_paths([filename])
                root.update()
                self.assertEqual(len(app.rows), 1)
                root.geometry("1040x700")
                root.update()
                self.assertLessEqual(app.pause_button.winfo_rooty() + app.pause_button.winfo_height(), root.winfo_rooty() + root.winfo_height())
                app.play_selected()
                self.assertEqual(player.state, "playing")
                playlist = db.create_playlist("My playlist")
                db.add_to_playlist(playlist, [app.rows[0]["id"]])
                app.refresh_playlists()
                app.playlists.selection_set(0)
                app.select_playlist()
                self.assertEqual(app.playlist_id, playlist)
                self.assertEqual(len(app.rows), 1)
                app.search.set("missing")
                self.assertEqual(app.rows, [])
                app.search.set("song")
                self.assertEqual(len(app.rows), 1)
                root.update()
            finally:
                app.close()
