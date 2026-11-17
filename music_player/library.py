"""SQLite persistence and portable playlist exchange. No audio data is copied."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

SUPPORTED = {".mp3", ".wav", ".ogg", ".flac"}


def data_directory() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    folder = base / "MusicPlayer"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


class Library:
    def __init__(self, path: str | Path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL, artist TEXT NOT NULL DEFAULT '',
                album TEXT NOT NULL DEFAULT '', duration REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE
                    CHECK(length(trim(name)) BETWEEN 1 AND 100)
            );
            CREATE TABLE IF NOT EXISTS playlist_tracks (
                playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                PRIMARY KEY (playlist_id, track_id)
            );
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)

    def close(self):
        self.connection.close()

    def setting(self, key, default=""):
        row = self.connection.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def save_setting(self, key, value):
        with self.connection:
            self.connection.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, str(value)))

    def add_track(self, filename: str | Path) -> int:
        path = Path(filename).expanduser().resolve()
        if path.suffix.lower() not in SUPPORTED:
            raise ValueError(f"Unsupported audio format: {path.name}")
        if not path.is_file():
            raise ValueError(f"File not found: {path}")
        title, artist, album, duration = path.stem, "", "", 0.0
        try:
            from mutagen import File
            audio = File(path, easy=True)
            if audio is not None:
                title = str(audio.get("title", [title])[0]) if audio.tags else title
                artist = str(audio.get("artist", [""])[0]) if audio.tags else ""
                album = str(audio.get("album", [""])[0]) if audio.tags else ""
                duration = float(audio.info.length)
        except (OSError, ValueError, KeyError, AttributeError):
            pass  # A file may still be playable even when its tags cannot be read.
        with self.connection:
            self.connection.execute("""INSERT INTO tracks(path,title,artist,album,duration)
                VALUES (?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET
                title=excluded.title, artist=excluded.artist, album=excluded.album,
                duration=excluded.duration""", (os.path.normcase(str(path)), title, artist, album, duration))
        return self.connection.execute("SELECT id FROM tracks WHERE path=?", (os.path.normcase(str(path)),)).fetchone()[0]

    def tracks(self, playlist_id=None, search=""):
        params = []
        sql = "SELECT t.* FROM tracks t"
        if playlist_id is not None:
            sql += " JOIN playlist_tracks p ON p.track_id=t.id WHERE p.playlist_id=?"
            params.append(playlist_id)
        else:
            sql += " WHERE 1=1"
        if search:
            sql += " AND (instr(lower(t.title),lower(?))>0 OR instr(lower(t.artist),lower(?))>0 OR instr(lower(t.album),lower(?))>0)"
            params.extend([search] * 3)
        sql += " ORDER BY p.position" if playlist_id is not None else " ORDER BY t.title COLLATE NOCASE, t.id"
        return [dict(r) for r in self.connection.execute(sql, params)]

    def playlists(self):
        return [dict(r) for r in self.connection.execute("""SELECT p.id,p.name,count(pt.track_id) AS count
            FROM playlists p LEFT JOIN playlist_tracks pt ON pt.playlist_id=p.id
            GROUP BY p.id ORDER BY p.name COLLATE NOCASE""")]

    @staticmethod
    def _name(name):
        name = name.strip()
        if not 1 <= len(name) <= 100:
            raise ValueError("Playlist names must contain 1–100 characters.")
        return name

    def create_playlist(self, name):
        with self.connection:
            return self.connection.execute("INSERT INTO playlists(name) VALUES (?)", (self._name(name),)).lastrowid

    def rename_playlist(self, playlist_id, name):
        with self.connection:
            self.connection.execute("UPDATE playlists SET name=? WHERE id=?", (self._name(name), playlist_id))

    def delete_playlist(self, playlist_id):
        with self.connection:
            self.connection.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))

    def add_to_playlist(self, playlist_id, track_ids):
        with self.connection:
            start = self.connection.execute("SELECT coalesce(max(position),-1)+1 FROM playlist_tracks WHERE playlist_id=?", (playlist_id,)).fetchone()[0]
            for offset, track_id in enumerate(dict.fromkeys(track_ids)):
                self.connection.execute("INSERT OR IGNORE INTO playlist_tracks VALUES (?,?,?)", (playlist_id, track_id, start + offset))

    def remove(self, track_ids, playlist_id=None):
        with self.connection:
            for track_id in track_ids:
                if playlist_id is None:
                    self.connection.execute("DELETE FROM tracks WHERE id=?", (track_id,))
                else:
                    self.connection.execute("DELETE FROM playlist_tracks WHERE playlist_id=? AND track_id=?", (playlist_id, track_id))

    def reorder(self, playlist_id, ordered_ids):
        actual = {r["id"] for r in self.tracks(playlist_id)}
        if len(ordered_ids) != len(actual) or set(ordered_ids) != actual:
            raise ValueError("The reordered list must contain every playlist track exactly once.")
        with self.connection:
            for position, track_id in enumerate(ordered_ids):
                self.connection.execute("UPDATE playlist_tracks SET position=? WHERE playlist_id=? AND track_id=?", (position, playlist_id, track_id))

    def import_m3u(self, filename):
        source = Path(filename)
        entries, errors = [], []
        for line in source.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            path = Path(line)
            if not path.is_absolute():
                path = source.parent / path
            try:
                entries.append(self.add_track(path))
            except ValueError as exc:
                errors.append(str(exc))
        return list(dict.fromkeys(entries)), errors

    def export_m3u(self, filename, playlist_id=None):
        target = Path(filename)
        lines = ["#EXTM3U"]
        for track in self.tracks(playlist_id):
            label = f"{track['artist']} - {track['title']}" if track["artist"] else track["title"]
            label = label.replace("\n", " ").replace("\r", " ")
            lines.extend([f"#EXTINF:{int(track['duration'])},{label}", track["path"]])
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
