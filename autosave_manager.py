"""Autosave support for Maestro Notepad."""

from __future__ import annotations

import os
from pathlib import Path
import time

from PyQt6.QtCore import QTimer


class AutoSaveManager:
    """Watch for changes and quietly save backup copies in the background."""

    def __init__(self, canvas, file_manager, save_path_getter, interval_ms=30000):
        self.canvas = canvas
        self.file_manager = file_manager
        self.get_path = save_path_getter
        self.interval_ms = interval_ms
        self.enabled = True
        self.last_hash = None
        self.last_save_time = 0

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._autosave)

    def start(self):
        """Hook the canvas to the timer and begin listening for changes."""

        self.canvas.scene.changed.connect(self.schedule_autosave)

    def stop(self):
        """Stop the timer when the window is closing."""

        self.timer.stop()

    def schedule_autosave(self):
        """Restart the timer each time something changes.

        This keeps Maestro from saving on every tiny mouse move.
        """

        if self.enabled:
            self.timer.start(self.interval_ms)

    def mark_clean(self):
        """Remember the newest saved state so we do not autosave the same thing twice."""

        self.last_hash = self._get_canvas_hash()
        self.last_save_time = time.time()

    def _autosave(self):
        """Save a backup file if we have a real project path and new changes."""

        if not self.enabled:
            return

        path = self.get_path()
        if not path:
            return

        current_hash = self._get_canvas_hash()
        if current_hash is None or current_hash == self.last_hash:
            return

        autosave_path = self.file_manager.autosave_path_for(path)
        self.file_manager.save_project(self.canvas, autosave_path)
        self.last_hash = current_hash
        self.last_save_time = time.time()

    def _get_canvas_hash(self):
        """Turn the canvas state into a quick change fingerprint."""

        try:
            return hash(str(self.canvas.serialize()))
        except Exception:
            return None

    def newer_autosave_path(self, project_path):
        """Return the backup path only if it is newer than the real project file."""

        if not project_path:
            return None

        project_file = self.file_manager.normalize_project_path(project_path)
        autosave_file = self.file_manager.autosave_path_for(project_file)

        if not os.path.exists(autosave_file):
            return None

        project_time = os.path.getmtime(project_file) if os.path.exists(project_file) else 0
        autosave_time = os.path.getmtime(autosave_file)
        if autosave_time > project_time:
            return autosave_file

        return None

    def clear_autosave(self):
        """Delete the backup file after a clean manual save if it exists."""

        path = self.get_path()
        if not path:
            return

        autosave_path = Path(self.file_manager.autosave_path_for(path))
        if autosave_path.exists():
            autosave_path.unlink()
