import os
import re
import UnityPy

# Bundles matching a001–a019 and a050–a052 contain character sprites.
_BUNDLE_RE = re.compile(r"^a0([0-1][0-9]|5[0-2])$")

_UNITYFS_MAGIC = b"UnityFS"


def load_bundle(path: str):
    """Load a Unity bundle, stripping any proprietary pre-header before UnityFS."""
    with open(path, "rb") as f:
        data = f.read()
    idx = data.find(_UNITYFS_MAGIC)
    if idx > 0:
        data = data[idx:]
    return UnityPy.load(data)


def find_streaming_assets(base_dir: str) -> str | None:
    """
    Given any folder inside (or equal to) a PARANORMASIGHT installation,
    return the path to the StreamingAssets subfolder.

    Accepts:
      - The base game folder  (e.g. .../PARANORMASIGHT_2/)
      - The Data folder       (e.g. .../PARANORMASIGHT_2_Data/)
      - StreamingAssets itself (returned as-is)
    """
    norm = os.path.normpath(base_dir)
    if os.path.basename(norm) == "StreamingAssets" and os.path.isdir(norm):
        return norm
    # Search immediate children for a *_Data/StreamingAssets pattern
    try:
        for name in sorted(os.listdir(base_dir)):
            if name.endswith("_Data"):
                candidate = os.path.join(base_dir, name, "StreamingAssets")
                if os.path.isdir(candidate):
                    return candidate
    except OSError:
        pass
    return None


def get_char_code(env):
    """Return the character code (e.g. 'avi') from the dice atlas name.
    Checks Sprite assets first, then Texture2D assets as a fallback."""
    for type_name in ("Sprite", "Texture2D"):
        for obj in env.objects:
            if obj.type.name == type_name:
                d = obj.read()
                m = re.match(r"dice_([a-z]+)", d.m_Name)
                if m:
                    return m.group(1)
    return None


class BundleScanner:
    """
    Scans a StreamingAssets directory for character asset bundles.

    Each entry in results:
      {"char_code": str, "display_name": str, "bundle_path": str,
       "bundle_name": str, "game_key": str}

    If catalog_entries is provided (list of (bundle_stem, display_name) tuples),
    only those bundles are opened; char_code is still read dynamically from each
    bundle's dice atlas.  If catalog_entries is None, all files matching the
    bundle name pattern are scanned and char_code is used as display_name.
    """

    def __init__(self, streaming_dir: str, game_key: str = "",
                 catalog_entries=None, progress_cb=None):
        self._streaming_dir = streaming_dir
        self._game_key = game_key
        self._catalog_entries = catalog_entries
        self._progress_cb = progress_cb

    def scan(self) -> list:
        if self._catalog_entries is not None:
            return self._scan_from_catalog()
        return self._scan_dynamic()

    def _scan_from_catalog(self) -> list:
        # Map stem → full path (handles any file extension the engine uses).
        stem_map: dict = {}
        try:
            for name in os.listdir(self._streaming_dir):
                stem = os.path.splitext(name)[0]
                if stem not in stem_map:
                    stem_map[stem] = os.path.join(self._streaming_dir, name)
        except OSError:
            return []

        results = []
        for bundle_stem, display_name in self._catalog_entries:
            path = stem_map.get(bundle_stem)
            if not path:
                continue
            try:
                env = load_bundle(path)
                char_code = get_char_code(env)
            except Exception:
                char_code = None
            if char_code:
                results.append({
                    "char_code": char_code,
                    "display_name": display_name,
                    "bundle_path": path,
                    "bundle_name": bundle_stem,
                    "game_key": self._game_key,
                })
        return results

    def _scan_dynamic(self) -> list:
        candidates = []
        try:
            entries = os.listdir(self._streaming_dir)
        except OSError:
            return []

        for name in sorted(entries):
            stem = os.path.splitext(name)[0]
            if _BUNDLE_RE.match(stem):
                candidates.append(os.path.join(self._streaming_dir, name))

        results = []
        total = len(candidates)
        for i, path in enumerate(candidates):
            try:
                env = load_bundle(path)
                code = get_char_code(env)
            except Exception:
                code = None

            if code:
                bname = os.path.splitext(os.path.basename(path))[0]
                results.append({
                    "char_code": code,
                    "display_name": code,
                    "bundle_path": path,
                    "bundle_name": bname,
                    "game_key": self._game_key,
                })

            if self._progress_cb:
                self._progress_cb(i + 1, total, code or "")

        return results
