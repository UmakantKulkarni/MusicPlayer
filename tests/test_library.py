import tempfile
import unittest
import wave
from pathlib import Path
from music_player.library import Library


def make_wave(path):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\0\0" * 8000)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = Library(self.root / "test.sqlite3")
        self.file = self.root / "Café song.wav"
        make_wave(self.file)
        self.track = self.db.add_track(self.file)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_metadata_duplicates_and_search(self):
        self.assertEqual(self.db.add_track(self.file), self.track)
        self.assertEqual(len(self.db.tracks()), 1)
        self.assertEqual(self.db.tracks()[0]["duration"], 1)
        self.assertEqual(len(self.db.tracks(search="song")), 1)
        self.assertEqual(self.db.tracks(search="' OR 1=1 --"), [])

    def test_playlist_crud_and_foreign_keys(self):
        playlist = self.db.create_playlist(" Focus ")
        self.db.add_to_playlist(playlist, [self.track, self.track])
        self.assertEqual(self.db.playlists()[0]["count"], 1)
        self.db.rename_playlist(playlist, "Work")
        self.assertEqual(self.db.playlists()[0]["name"], "Work")
        self.db.remove([self.track], playlist)
        self.assertEqual(self.db.tracks(playlist), [])
        self.assertEqual(len(self.db.tracks()), 1)
        self.db.add_to_playlist(playlist, [self.track])
        self.db.delete_playlist(playlist)
        self.assertEqual(self.db.connection.execute("SELECT count(*) FROM playlist_tracks").fetchone()[0], 0)
        self.assertTrue(self.file.exists())

    def test_validation_and_cascade(self):
        import sqlite3
        playlist = self.db.create_playlist("Mix")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.create_playlist("mix")
        with self.assertRaises(ValueError):
            self.db.create_playlist(" ")
        with self.assertRaises(ValueError):
            self.db.add_track(self.root / "missing.mp3")
        with self.assertRaises(ValueError):
            self.db.add_track(self.root / "bad.exe")
        self.db.add_to_playlist(playlist, [self.track])
        self.db.remove([self.track])
        self.assertEqual(self.db.tracks(playlist), [])
        self.assertTrue(self.file.exists())

    def test_order_and_reopen(self):
        other = self.root / "second.wav"
        make_wave(other)
        second = self.db.add_track(other)
        playlist = self.db.create_playlist("Ordered")
        self.db.add_to_playlist(playlist, [self.track, second])
        self.db.reorder(playlist, [second, self.track])
        with self.assertRaises(ValueError):
            self.db.reorder(playlist, [second, second])
        self.db.save_setting("volume", "42")
        self.db.close()
        self.db = Library(self.root / "test.sqlite3")
        self.assertEqual([t["id"] for t in self.db.tracks(playlist)], [second, self.track])
        self.assertEqual(self.db.setting("volume"), "42")

    def test_m3u_roundtrip_and_relative_missing_paths(self):
        playlist = self.db.create_playlist("Mix")
        self.db.add_to_playlist(playlist, [self.track])
        exported = self.root / "mix.m3u8"
        self.db.export_m3u(exported, playlist)
        ids, errors = self.db.import_m3u(exported)
        self.assertEqual(ids, [self.track])
        self.assertEqual(errors, [])
        exported.write_text("#EXTM3U\nCafé song.wav\nmissing.mp3\nhttps://example.com/music.mp3\n", encoding="utf-8")
        ids, errors = self.db.import_m3u(exported)
        self.assertEqual(ids, [self.track])
        self.assertEqual(len(errors), 2)
