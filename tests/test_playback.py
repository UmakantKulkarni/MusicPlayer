import unittest
from unittest.mock import Mock
from music_player.playback import Player


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.time = 100.0
        self.backend = Mock()
        self.backend.get_busy.return_value = True
        self.player = Player(self.backend, clock=lambda: self.time)
        self.tracks = [dict(id=i, path=f"song{i}.mp3", duration=60) for i in range(3)]

    def test_pause_resume_clock_and_volume(self):
        self.player.play_queue(self.tracks)
        self.time += 4
        self.assertEqual(self.player.position, 4)
        self.player.toggle_pause()
        self.time += 20
        self.assertEqual(self.player.position, 4)
        self.player.toggle_pause()
        self.time += 2
        self.assertEqual(self.player.position, 6)
        self.player.set_volume(2)
        self.backend.set_volume.assert_called_with(1.0)

    def test_queue_completion_repeat_and_previous(self):
        self.player.play_queue(self.tracks)
        self.player.next()
        self.assertEqual(self.player.current["id"], 1)
        self.player.previous()
        self.assertEqual(self.player.current["id"], 0)
        self.player.play_queue(self.tracks, 2)
        self.player.next(automatic=True)
        self.assertEqual(self.player.state, "stopped")
        self.player.repeat = "all"
        self.player.next()
        self.assertEqual(self.player.current["id"], 0)
        self.player.repeat = "one"
        self.backend.get_busy.return_value = False
        self.player.poll()
        self.assertEqual(self.player.current["id"], 0)
        self.assertEqual(self.player.state, "playing")

    def test_shuffle_and_history(self):
        self.player.shuffle = True
        self.player.play_queue(self.tracks)
        self.player.next()
        self.assertNotEqual(self.player.current["id"], 0)
        self.player.previous()
        self.assertEqual(self.player.current["id"], 0)

    def test_seek_preserves_pause_and_wav_limitation(self):
        self.player.play_queue(self.tracks)
        self.player.toggle_pause()
        self.player.seek(20)
        self.assertEqual(self.player.state, "paused")
        self.assertEqual(self.player.position, 20)
        self.backend.play.assert_called_with(start=20.0)
        self.player.queue[0] = dict(path="audio.wav", duration=10)
        with self.assertRaises(ValueError):
            self.player.seek(2)

    def test_close_releases_windows_file_handle(self):
        self.player.play_queue(self.tracks)
        self.player.close()
        self.backend.unload.assert_called_once()
        self.assertEqual(self.player.state, "stopped")

    def test_load_failure_stops_previous_audio(self):
        self.player.play_queue(self.tracks)
        self.backend.load.side_effect = RuntimeError("Missing file")
        with self.assertRaises(RuntimeError):
            self.player.next()
        self.assertEqual(self.player.state, "stopped")


if __name__ == "__main__":
    unittest.main()
