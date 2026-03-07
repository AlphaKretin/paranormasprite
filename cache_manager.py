import json
import os

_META_FILE = "cache_meta.json"
_VERSION = 2  # bumped: key is now bundle_path, entries include game_key

# Synthetic bundle_path prefix for cache-imported characters (no real bundle file).
IMPORTED_PREFIX = "__imported__/"


class CacheManager:
    def __init__(self, cache_dir: str):
        self._cache_dir = cache_dir
        self._meta_path = os.path.join(cache_dir, _META_FILE)
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self._meta_path):
            try:
                with open(self._meta_path, encoding="utf-8") as f:
                    d = json.load(f)
                if d.get("version") == _VERSION:
                    return d
            except Exception:
                pass
        return {"version": _VERSION, "characters": {}}

    def _save(self):
        os.makedirs(self._cache_dir, exist_ok=True)
        with open(self._meta_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def _sprites_dir(self, game_key: str, char_code: str) -> str:
        """Sprites for a character live at {cache_dir}/{game_key}/{char_code}/."""
        return os.path.join(self._cache_dir, game_key, char_code)

    def is_extracted(self, bundle_path: str, char_code: str, game_key: str) -> bool:
        if bundle_path.startswith(IMPORTED_PREFIX):
            # Imported character — sprites are pre-provided; just check the dir exists.
            return os.path.isdir(self._sprites_dir(game_key, char_code))
        chars = self._data.get("characters", {})
        entry = chars.get(bundle_path)
        if entry is None:
            return False
        try:
            mtime = os.path.getmtime(bundle_path)
        except OSError:
            return False
        if entry.get("bundle_mtime") != mtime:
            return False
        return os.path.isdir(self._sprites_dir(game_key, char_code))

    def record_extracted(self, bundle_path: str, char_code: str,
                         game_key: str, sprite_count: int):
        try:
            mtime = os.path.getmtime(bundle_path)
        except OSError:
            mtime = 0.0
        self._data.setdefault("characters", {})[bundle_path] = {
            "char_code": char_code,
            "game_key": game_key,
            "bundle_mtime": mtime,
            "sprite_count": sprite_count,
        }
        self._save()

    def extracted_chars(self) -> set:
        """Returns the set of bundle_paths that have been successfully extracted."""
        return set(self._data.get("characters", {}).keys())

    def record_cache_data(self, char_entry: dict):
        """Add or update a character entry in cache_data.json."""
        path = os.path.join(self._cache_dir, "cache_data.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") != 1:
                data = {"version": 1, "characters": []}
        except Exception:
            data = {"version": 1, "characters": []}
        chars     = data["characters"]
        char_code = char_entry.get("char_code", "")
        game_key  = char_entry.get("game_key", "")
        for i, c in enumerate(chars):
            if c.get("char_code") == char_code and c.get("game_key") == game_key:
                chars[i] = char_entry
                break
        else:
            chars.append(char_entry)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
