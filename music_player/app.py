"""Tkinter desktop application. All Tk operations stay on the main thread."""
from __future__ import annotations

import logging
import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .library import Library, SUPPORTED, data_directory
from .playback import Player

BG, PANEL, TEXT, MUTED, ACCENT = "#10141e", "#1b2232", "#edf1fb", "#a3aec5", "#7de1b9"


def duration(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


class App:
    def __init__(self, root, library=None, player=None):
        self.root = root
        self.library = library or Library(data_directory() / "library.sqlite3")
        self.player = player
        self.playlist_id = None
        self.rows = []
        self.importing = False
        self.closed = False
        self.seeking = False
        self.after_id = None
        self.root.title("Music Player • Playlist Management")
        self.root.geometry("1120x740")
        self.root.minsize(1040, 700)
        self.root.configure(bg=BG)
        self._styles()
        self._layout()
        self.refresh_playlists()
        self.refresh_tracks()
        if self.player is None:
            self.connect_audio()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Control-o>", lambda e: self.import_files())
        self.root.bind("<Control-n>", lambda e: self.create_playlist())
        self.root.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        self._tick()

    def _styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Title.TLabel", font=("Segoe UI", 25, "bold"))
        style.configure("TButton", background=PANEL, foreground=TEXT, padding=(12, 9), borderwidth=0, font=("Segoe UI", 10))
        style.map("TButton", background=[("active", "#303d55"), ("disabled", PANEL)], foreground=[("disabled", "#677185")])
        style.configure("Accent.TButton", background=ACCENT, foreground="#10261e", font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#a2f0d0")])
        style.configure("TEntry", fieldbackground=PANEL, foreground=TEXT, insertcolor=TEXT, padding=9)
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=36, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=BG, foreground=MUTED, padding=10, font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", "#334f51")], foreground=[("selected", "#ffffff")])
        style.configure("TScale", background=BG, troughcolor=PANEL)
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", BG)])

    def button(self, parent, text, command, accent=False):
        b = ttk.Button(parent, text=text, command=lambda: self.safe(command), style="Accent.TButton" if accent else "TButton")
        b.pack(side="left", padx=(0, 7))
        return b

    def _layout(self):
        shell = ttk.Frame(self.root, padding=24)
        shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 22))
        ttk.Label(header, text="♫  Music Player", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="YOUR MUSIC. YOUR ORDER.", style="Muted.TLabel").pack(side="right")
        body = ttk.Frame(shell)
        body.grid(row=1, column=0, sticky="nsew")
        sidebar = ttk.Frame(body, width=205)
        sidebar.pack(side="left", fill="y", padx=(0, 22))
        sidebar.pack_propagate(False)
        ttk.Label(sidebar, text="COLLECTION", style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Button(sidebar, text="All music", command=self.show_library).pack(fill="x")
        ttk.Label(sidebar, text="PLAYLISTS", style="Muted.TLabel").pack(anchor="w", pady=(24, 8))
        self.playlists = tk.Listbox(sidebar, bg=PANEL, fg=TEXT, selectbackground="#334f51", selectforeground="white", relief="flat", borderwidth=0, highlightthickness=0, font=("Segoe UI", 11), activestyle="none", exportselection=False, height=3)
        self.playlists.pack(fill="both", expand=True)
        self.playlists.bind("<<ListboxSelect>>", self.select_playlist)
        self.playlist_keys = []
        for text, command in [("+ New playlist", self.create_playlist), ("Rename playlist", self.rename_playlist), ("Delete playlist", self.delete_playlist), ("Import M3U playlist", self.import_playlist), ("Export M3U playlist", self.export_playlist)]:
            ttk.Button(sidebar, text=text, command=lambda c=command: self.safe(c)).pack(fill="x", pady=(7, 0))
        content = ttk.Frame(body)
        content.pack(side="left", fill="both", expand=True)
        self.heading = ttk.Label(content, text="All music", font=("Segoe UI", 20, "bold"))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(3, weight=1)
        self.heading.grid(row=0, column=0, sticky="w")
        self.summary = ttk.Label(content, style="Muted.TLabel")
        self.summary.grid(row=1, column=0, sticky="w", pady=(4, 14))
        toolbar = ttk.Frame(content)
        toolbar.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self.button(toolbar, "+ Add files", self.import_files, True)
        self.button(toolbar, "Add folder", self.import_folder)
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *args: self.refresh_tracks())
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search, width=20)
        self.search_entry.pack(side="right", fill="x", expand=True, padx=(10, 0))
        ttk.Label(toolbar, text="Search", style="Muted.TLabel").pack(side="right")
        table = ttk.Frame(content)
        table.grid(row=3, column=0, sticky="nsew")
        self.tree = ttk.Treeview(table, columns=("title", "artist", "album", "duration"), show="headings", selectmode="extended")
        for key, label, width in [("title", "TITLE", 250), ("artist", "ARTIST", 140), ("album", "ALBUM", 140), ("duration", "TIME", 65)]:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=55, stretch=key != "duration")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.safe(self.play_selected))
        self.tree.bind("<Return>", lambda e: self.safe(self.play_selected))
        actions = ttk.Frame(content)
        actions.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self.button(actions, "Play", self.play_selected, True)
        self.button(actions, "Add to playlist", self.add_selected)
        self.button(actions, "Remove", self.remove_selected)
        self.button(actions, "↑", lambda: self.move(-1))
        self.button(actions, "↓", lambda: self.move(1))
        self.now = ttk.Label(shell, text="Ready when you are", font=("Segoe UI", 13, "bold"))
        self.now.grid(row=2, column=0, sticky="w", pady=(23, 6))
        self.progress = ttk.Scale(shell, from_=0, to=1, command=lambda v: None)
        self.progress.grid(row=3, column=0, sticky="ew")
        self.progress.bind("<ButtonPress-1>", lambda e: setattr(self, "seeking", True))
        self.progress.bind("<ButtonRelease-1>", self.finish_seek)
        self.progress.bind("<KeyRelease>", lambda e: self.safe(lambda: self.seek(float(self.progress.get()))))
        controls = ttk.Frame(shell)
        controls.grid(row=4, column=0, sticky="ew", pady=(8, 8))
        self.button(controls, "|◀", lambda: self.audio_action("previous"))
        self.pause_button = self.button(controls, "Play / Pause", self.toggle_pause, True)
        self.button(controls, "▶|", lambda: self.audio_action("next"))
        self.button(controls, "Stop", lambda: self.audio_action("stop"))
        self.shuffle = tk.BooleanVar()
        ttk.Checkbutton(controls, text="Shuffle", variable=self.shuffle, command=self.set_shuffle).pack(side="left", padx=8)
        self.repeat_button = self.button(controls, "Repeat: off", self.cycle_repeat)
        self.time = ttk.Label(controls, text="0:00 / 0:00", style="Muted.TLabel")
        self.time.pack(side="left", padx=8)
        self.volume = ttk.Scale(controls, from_=0, to=100, command=self.set_volume, length=110)
        self.volume.set(float(self.library.setting("volume", "70")))
        self.volume.pack(side="right")
        ttk.Label(controls, text="Volume", style="Muted.TLabel").pack(side="right", padx=8)
        self.status = tk.StringVar(value="Add audio files or a folder to begin. Double-click a track to play.")
        ttk.Label(shell, textvariable=self.status, style="Muted.TLabel", wraplength=1000).grid(row=5, column=0, sticky="w")

    def safe(self, callback):
        try:
            return callback()
        except sqlite3.IntegrityError:
            messagebox.showerror("Playlist name", "That playlist name already exists. Choose another name.", parent=self.root)
        except Exception as exc:
            logging.exception("Operation failed")
            messagebox.showerror("Unable to complete action", str(exc), parent=self.root)

    def connect_audio(self):
        try:
            self.player = Player()
            self.set_volume(self.volume.get())
            return True
        except Exception as exc:
            self.status.set(f"Audio device unavailable: {exc}. Connect an output device and press Play to retry.")
            return False

    def ensure_audio(self):
        return self.player is not None or self.connect_audio()

    def audio_action(self, method):
        if self.ensure_audio():
            getattr(self.player, method)()

    def selected_ids(self):
        return [int(i) for i in self.tree.selection()]

    def refresh_playlists(self):
        self.playlists.delete(0, "end")
        items = self.library.playlists()
        self.playlist_keys = [p["id"] for p in items]
        for index, p in enumerate(items):
            self.playlists.insert("end", f"{p['name']}  ({p['count']})")
            if p["id"] == self.playlist_id:
                self.playlists.selection_set(index)
                self.heading.configure(text=p["name"])

    def refresh_tracks(self):
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        self.rows = self.library.tracks(self.playlist_id, self.search.get())
        for track in self.rows:
            self.tree.insert("", "end", iid=str(track["id"]), values=(track["title"], track["artist"] or "Unknown artist", track["album"] or "—", duration(track["duration"])))
        self.tree.selection_set([i for i in selected if self.tree.exists(i)])
        total = sum(t["duration"] for t in self.rows)
        self.summary.configure(text=f"{len(self.rows)} tracks · {duration(total)} total" + (" · No matches" if self.search.get() and not self.rows else ""))

    def show_library(self):
        self.playlist_id = None
        self.playlists.selection_clear(0, "end")
        self.heading.configure(text="All music")
        self.search.set("")
        self.refresh_tracks()

    def select_playlist(self, event=None):
        selection = self.playlists.curselection()
        if selection and selection[0] < len(self.playlist_keys):
            self.playlist_id = self.playlist_keys[selection[0]]
            self.search.set("")
            self.refresh_playlists()
            self.refresh_tracks()

    def create_playlist(self):
        name = simpledialog.askstring("New playlist", "Playlist name:", parent=self.root)
        if name is not None:
            self.playlist_id = self.library.create_playlist(name)
            self.search.set("")
            self.refresh_playlists()
            self.refresh_tracks()

    def rename_playlist(self):
        if self.playlist_id is None:
            self.status.set("Select a playlist to rename.")
            return
        name = simpledialog.askstring("Rename playlist", "New name:", initialvalue=self.heading.cget("text"), parent=self.root)
        if name is not None:
            self.library.rename_playlist(self.playlist_id, name)
            self.refresh_playlists()

    def delete_playlist(self):
        if self.playlist_id is not None and messagebox.askyesno("Delete playlist", "Delete this playlist? Your audio files and library tracks will be kept.", parent=self.root):
            self.library.delete_playlist(self.playlist_id)
            self.show_library()
            self.refresh_playlists()

    def import_files(self):
        files = filedialog.askopenfilenames(parent=self.root, title="Add audio files", filetypes=[("Audio files", "*.mp3 *.wav *.ogg *.flac"), ("All files", "*.*")])
        self.import_paths(files)

    def import_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title="Add folder (includes subfolders)")
        if folder:
            # Directory traversal and metadata work are incremental so Tk stays responsive.
            self.import_paths(p for p in Path(folder).rglob("*") if p.suffix.lower() in SUPPORTED and p.is_file())

    def import_paths(self, paths):
        if self.importing:
            self.status.set("Please wait for the current import to finish.")
            return
        iterator = iter(paths)
        self.importing = True
        target = self.playlist_id
        added, errors = [], []

        def step():
            if self.closed:
                return
            try:
                for _ in range(8):
                    path = next(iterator)
                    try:
                        added.append(self.library.add_track(path))
                    except Exception as exc:
                        errors.append(f"{Path(path).name}: {exc}")
                self.status.set(f"Importing… {len(added)} files processed")
                self.root.after(1, step)
            except StopIteration:
                finish()
            except Exception as exc:
                errors.append(str(exc))
                finish()

        def finish():
            self.importing = False
            if target is not None and target in [p["id"] for p in self.library.playlists()]:
                self.library.add_to_playlist(target, added)
            self.refresh_playlists()
            self.refresh_tracks()
            self.status.set(f"Imported {len(set(added))} tracks. {len(errors)} files skipped.")
            if errors:
                messagebox.showwarning("Import results", "\n".join(errors[:12]), parent=self.root)
        step()

    def add_selected(self):
        ids = self.selected_ids()
        if not ids:
            self.status.set("Select one or more tracks first (Ctrl/Shift selects multiple).")
            return
        playlists = self.library.playlists()
        if not playlists:
            self.status.set("Create a playlist first, then select tracks to add.")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Add to playlist")
        dialog.transient(self.root)
        dialog.configure(bg=BG)
        ttk.Label(dialog, text="Choose a playlist", padding=15).pack()
        options = tk.Listbox(dialog, width=40, height=min(12, len(playlists)), exportselection=False)
        options.pack(padx=15)
        for p in playlists:
            options.insert("end", p["name"])
        options.selection_set(0)

        def add():
            selected = options.curselection()
            if selected:
                self.library.add_to_playlist(playlists[selected[0]]["id"], ids)
                self.refresh_playlists()
                self.refresh_tracks()
                self.status.set(f"Added {len(ids)} selected tracks to {playlists[selected[0]]['name']}.")
                dialog.destroy()
        ttk.Button(dialog, text="Add selected tracks", command=lambda: self.safe(add)).pack(pady=15)
        dialog.grab_set()

    def remove_selected(self):
        ids = self.selected_ids()
        if not ids:
            return
        text = "Remove selected tracks from this playlist?" if self.playlist_id is not None else "Remove selected tracks from the library and all playlists? Audio files on disk will be kept."
        if messagebox.askyesno("Remove tracks", text, parent=self.root):
            if self.player and self.player.current and self.player.current["id"] in ids:
                self.player.stop()
            self.library.remove(ids, self.playlist_id)
            if self.player:
                self.player.stop()
                self.player.queue = []  # Do not keep stale queue entries after library edits.
                self.player.index = -1
            self.refresh_playlists()
            self.refresh_tracks()

    def move(self, direction):
        ids = self.selected_ids()
        if self.playlist_id is None or self.search.get() or len(ids) != 1:
            self.status.set("To reorder: open a playlist, clear search, and select one track.")
            return
        order = [t["id"] for t in self.rows]
        index = order.index(ids[0])
        other = index + direction
        if 0 <= other < len(order):
            order[index], order[other] = order[other], order[index]
            self.library.reorder(self.playlist_id, order)
            self.refresh_tracks()
            self.tree.see(str(ids[0]))

    def import_playlist(self):
        if self.importing:
            self.status.set("Wait for the current import to finish.")
            return
        filename = filedialog.askopenfilename(parent=self.root, filetypes=[("M3U playlists", "*.m3u *.m3u8")])
        if filename:
            ids, errors = self.library.import_m3u(filename)
            name, number = Path(filename).stem, 2
            existing = {p["name"].casefold() for p in self.library.playlists()}
            base = name[:90] or "Imported playlist"
            name = base
            while name.casefold() in existing:
                name = f"{base} ({number})"
                number += 1
            self.playlist_id = self.library.create_playlist(name)
            self.library.add_to_playlist(self.playlist_id, ids)
            self.search.set("")
            self.refresh_playlists()
            self.refresh_tracks()
            self.status.set(f"Imported playlist: {len(ids)} tracks, {len(errors)} skipped. M3U supports local files only.")
            if errors:
                messagebox.showwarning("Files skipped", "\n".join(errors[:12]), parent=self.root)

    def export_playlist(self):
        filename = filedialog.asksaveasfilename(parent=self.root, defaultextension=".m3u8", filetypes=[("UTF-8 M3U playlist", "*.m3u8")])
        if filename:
            self.library.export_m3u(filename, self.playlist_id)
            self.status.set("Playlist exported. It references your existing audio files; it does not copy them.")

    def play_selected(self):
        if not self.rows:
            self.status.set("Add audio files to start listening.")
            return
        if self.ensure_audio():
            ids = self.selected_ids()
            index = next((i for i, r in enumerate(self.rows) if ids and r["id"] == ids[0]), 0)
            self.player.play_queue(self.rows, index)
            self.status.set("Playing from the current view. Double-click another track to change the queue.")

    def toggle_pause(self):
        if self.ensure_audio():
            if self.player.current:
                self.player.toggle_pause()
            else:
                self.play_selected()

    def finish_seek(self, event=None):
        self.seeking = False
        self.safe(lambda: self.seek(float(self.progress.get())))

    def seek(self, seconds):
        if self.player:
            self.player.seek(seconds)

    def set_volume(self, value):
        if self.player:
            self.player.set_volume(float(value) / 100)

    def set_shuffle(self):
        if self.player:
            self.player.shuffle = self.shuffle.get()

    def cycle_repeat(self):
        if self.ensure_audio():
            modes = ["off", "all", "one"]
            self.player.repeat = modes[(modes.index(self.player.repeat) + 1) % 3]
            self.repeat_button.configure(text=f"Repeat: {self.player.repeat}")

    def _tick(self):
        if self.closed:
            return
        if self.player:
            try:
                self.player.poll()
            except Exception as exc:
                self.player.stop()
                self.status.set(f"Playback stopped: {exc}. Select another track to continue.")
            track = self.player.current
            if track:
                self.now.configure(text=f"{track['title']}  ·  {track['artist'] or 'Unknown artist'}")
                length = track["duration"]
                self.progress.configure(to=max(1, length))
                if not self.seeking:
                    self.progress.set(min(self.player.position, length) if length else 0)
                self.time.configure(text=f"{duration(self.player.position)} / {duration(length)}")
            else:
                self.now.configure(text="Ready when you are")
                self.progress.set(0)
                self.time.configure(text="0:00 / 0:00")
            self.pause_button.configure(text="Pause" if self.player.state == "playing" else "Play")
        self.after_id = self.root.after(200, self._tick)

    def close(self):
        self.closed = True
        if self.after_id:
            self.root.after_cancel(self.after_id)
        if self.player:
            self.player.close()
        self.library.save_setting("volume", self.volume.get())
        self.library.close()
        self.root.destroy()


def main():
    folder = data_directory()
    logging.basicConfig(filename=folder / "music-player.log", level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    root = tk.Tk()
    try:
        App(root)
        root.mainloop()
    except Exception as exc:
        logging.exception("Application startup failed")
        messagebox.showerror("Music Player", f"The application could not start: {exc}\nSee {folder / 'music-player.log'}", parent=root)
        root.destroy()
        raise
