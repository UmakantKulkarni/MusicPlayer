"""Playback state, queue traversal and audio backend, independent of the UI."""
from __future__ import annotations
import random
import time


class Player:
    def __init__(self, backend=None, clock=time.monotonic):
        if backend is None:
            import pygame
            pygame.mixer.init()
            backend = pygame.mixer.music
        self.backend = backend
        self.clock = clock
        self.queue = []
        self.index = -1
        self.state = "stopped"
        self.shuffle = False
        self.repeat = "off"
        self.volume = 0.7
        self.offset = 0.0
        self.started = 0.0
        self.history = []
        self.backend.set_volume(self.volume)

    @property
    def current(self):
        return self.queue[self.index] if 0 <= self.index < len(self.queue) else None

    @property
    def position(self):
        return self.offset + (max(0, self.clock() - self.started) if self.state == "playing" else 0)

    def play_queue(self, tracks, index=0):
        if not tracks or not 0 <= index < len(tracks):
            return
        self.stop()
        self.queue = list(tracks)
        self.history = []
        self.index = index
        self._play()

    def _play(self):
        self.state = "stopped"
        self.offset = 0.0
        self.backend.stop()
        self.backend.load(self.current["path"])
        self.backend.play()
        self.started = self.clock()
        self.state = "playing"

    def toggle_pause(self):
        if self.state == "playing":
            self.offset = self.position
            self.backend.pause()
            self.state = "paused"
        elif self.state == "paused":
            self.backend.unpause()
            self.started = self.clock()
            self.state = "playing"
        elif self.current:
            self._play()

    def stop(self):
        self.backend.stop()
        self.state = "stopped"
        self.offset = 0.0

    def close(self):
        self.stop()
        self.backend.unload()  # Release the file handle on Windows before exit.

    def set_volume(self, value):
        self.volume = max(0.0, min(1.0, float(value)))
        self.backend.set_volume(self.volume)

    def seek(self, seconds):
        if not self.current or self.state == "stopped":
            return
        # SDL_mixer supports reliable random access for MP3/OGG/FLAC, not WAV.
        if self.current["path"].lower().endswith(".wav"):
            raise ValueError("Seeking WAV files is unavailable. MP3, OGG and FLAC support seeking.")
        seconds = max(0.0, min(float(seconds), self.current["duration"]))
        paused = self.state == "paused"
        self.backend.play(start=seconds)
        self.offset, self.started = seconds, self.clock()
        if paused:
            self.backend.pause()

    def next(self, automatic=False):
        if not self.current:
            return
        if automatic and self.repeat == "one":
            self._play()
            return
        self.history.append(self.index)
        if self.shuffle and len(self.queue) > 1:
            choices = [i for i in range(len(self.queue)) if i != self.index]
            self.index = random.choice(choices)
        elif self.index + 1 < len(self.queue):
            self.index += 1
        elif self.repeat == "all":
            self.index = 0
        else:
            self.stop()
            return
        self._play()

    def previous(self):
        if not self.current:
            return
        if self.position > 3:
            self._play()
            return
        if self.history:
            self.index = self.history.pop()
        else:
            self.index = max(0, self.index - 1)
        self._play()

    def poll(self):
        if self.state == "playing" and not self.backend.get_busy():
            self.next(automatic=True)
