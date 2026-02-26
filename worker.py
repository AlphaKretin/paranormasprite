import os
import sys

from PySide6.QtCore import QThread, Signal

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from reconstruct_sprites import process_bundle  # noqa: E402


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
