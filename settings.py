import json

from PySide6.QtCore import QSettings


class SettingsManager:
    _APP = "ParanormaSprite"
    _ORG = "paranormasprite"

    def __init__(self):
        self._qs = QSettings(self._ORG, self._APP)

    @property
    def game_dirs(self) -> list:
        val = self._qs.value("game_dirs", "[]", type=str)
        try:
            return json.loads(val)
        except Exception:
            return []

    @game_dirs.setter
    def game_dirs(self, dirs: list):
        self._qs.setValue("game_dirs", json.dumps(dirs))

    @property
    def cache_dir(self) -> str:
        return self._qs.value("cache_dir", "", type=str)

    @cache_dir.setter
    def cache_dir(self, path: str):
        self._qs.setValue("cache_dir", path)

    def save_geometry(self, geometry: bytes):
        self._qs.setValue("geometry", geometry)

    def load_geometry(self) -> bytes | None:
        return self._qs.value("geometry", None)
