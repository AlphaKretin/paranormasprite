import os
import sys

from PySide6.QtCore import QThread, Signal

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bundle_data import BundleData, serialise_for_cache  # noqa: E402
from reconstruct_sprites import process_bundle            # noqa: E402


class ExtractAllWorker(QThread):
    """Extracts sprites for a list of characters sequentially."""
    progress  = Signal(int, int, str)  # current_index, total, display_name
    char_done = Signal(str)            # bundle_path
    finished  = Signal(int, int)       # success_count, error_count

    def __init__(self, entries: list, cache_dir: str, cache_manager, parent=None):
        super().__init__(parent)
        self._entries       = entries
        self._cache_dir     = cache_dir
        self._cache_manager = cache_manager
        self._cancelled     = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        total  = len(self._entries)
        errors = 0
        for i, entry in enumerate(self._entries):
            if self._cancelled:
                break
            self.progress.emit(i, total, entry["display_name"])
            try:
                out_dir = os.path.join(self._cache_dir, entry["game_key"])
                process_bundle(entry["bundle_path"], out_dir)
                char_dir = os.path.join(out_dir, entry["char_code"])
                sprite_count = len([
                    f for f in os.listdir(char_dir) if f.endswith(".png")
                ]) if os.path.isdir(char_dir) else 0
                self._cache_manager.record_extracted(
                    entry["bundle_path"], entry["char_code"],
                    entry["game_key"], sprite_count)
                try:
                    bd = BundleData(entry["bundle_path"])
                    self._cache_manager.record_cache_data(
                        serialise_for_cache(entry, bd))
                except Exception:
                    pass  # Non-fatal — viewer still works without cache_data.json
                self.char_done.emit(entry["bundle_path"])
            except Exception:
                errors += 1
        self.finished.emit(total - errors, errors)


class ExtractionWorker(QThread):
    progress = Signal(int, int, str)   # current, total, message
    finished = Signal(str)             # char_code
    error = Signal(str, str)           # char_code, error message

    def __init__(self, bundle_path: str, char_code: str, game_key: str,
                 cache_dir: str, cache_manager, parent=None):
        super().__init__(parent)
        self._bundle_path = bundle_path
        self._char_code = char_code
        self._game_key = game_key
        self._cache_dir = cache_dir
        self._cache_manager = cache_manager

    def run(self):
        try:
            # Sprites go into {cache_dir}/{game_key}/{char_code}/
            out_dir = os.path.join(self._cache_dir, self._game_key)
            process_bundle(self._bundle_path, out_dir)

            char_dir = os.path.join(out_dir, self._char_code)
            sprite_count = len([
                f for f in os.listdir(char_dir) if f.endswith(".png")
            ]) if os.path.isdir(char_dir) else 0

            self._cache_manager.record_extracted(
                self._bundle_path, self._char_code,
                self._game_key, sprite_count)
            self.finished.emit(self._char_code)
        except Exception as e:
            self.error.emit(self._char_code, str(e))
