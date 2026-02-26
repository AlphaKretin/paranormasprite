import os
import sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from bundle_data import BundleData, expr_unique
from bundle_catalog import BUNDLE_CATALOG, game_key_for_path
from cache_manager import CacheManager
from portrait_engine import PortraitEngine
from preview_widget import PreviewWidget
from scanner import BundleScanner, find_streaming_assets
from settings import SettingsManager
from ui_controls import ControlPanel
from worker import ExtractionWorker

# Standard Steam base folders for both PARANORMASIGHT games.
_STEAM_GAME_PATHS = [
    "C:/Program Files (x86)/Steam/steamapps/common/PARANORMASIGHT/",
    "C:/Program Files (x86)/Steam/steamapps/common/PARANORMASIGHT_2/",
]

# Cache folder: next to the exe (packaged) or next to this script (dev).
_APP_DIR = (
    os.path.dirname(sys.executable)
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__))
)
_DEFAULT_CACHE = os.path.join(_APP_DIR, "cache")


class _ScanThread(QThread):
    done  = Signal(list)
    diag  = Signal(str)   # emitted on empty results or exception

    def __init__(self, game_dirs: list, parent=None):
        super().__init__(parent)
        self._game_dirs = game_dirs

    def run(self):
        import traceback
        try:
            results = []
            seen_paths = set()
            log = []
            for game_dir in self._game_dirs:
                streaming = find_streaming_assets(game_dir)
                if streaming is None:
                    log.append(f"✗ No StreamingAssets found in: {game_dir}")
                    continue
                log.append(f"✓ StreamingAssets: {streaming}")
                game_key = game_key_for_path(streaming) or ""
                log.append(f"  game_key: {game_key!r}")
                catalog = BUNDLE_CATALOG.get(game_key) if game_key else None
                entries = catalog if catalog else None

                # Diagnostics: list actual files vs catalog stems
                try:
                    actual_stems = sorted(
                        os.path.splitext(f)[0]
                        for f in os.listdir(streaming)
                    )
                    log.append(f"  files in dir ({len(actual_stems)}): {actual_stems[:8]}")
                    if entries:
                        cat_stems = [s for s, _ in entries]
                        matched = [s for s in cat_stems if s in actual_stems]
                        log.append(f"  catalog stems matched: {matched[:8]} / {len(cat_stems)} total")
                        # Try get_char_code on the first matched bundle
                        if matched:
                            from scanner import get_char_code, load_bundle
                            test_path = os.path.join(streaming, matched[0])
                            # find actual file with that stem
                            for f in os.listdir(streaming):
                                if os.path.splitext(f)[0] == matched[0]:
                                    test_path = os.path.join(streaming, f)
                                    break
                            try:
                                env = load_bundle(test_path)
                                types_seen = list({o.type.name for o in env.objects})
                                code = get_char_code(env)
                                log.append(f"  test bundle '{matched[0]}': types={types_seen}, char_code={code!r}")
                            except Exception as ex:
                                log.append(f"  test bundle error: {ex}")
                except Exception as ex:
                    log.append(f"  dir listing error: {ex}")

                scan_results = BundleScanner(streaming, game_key, entries).scan()
                log.append(f"  entries found: {len(scan_results)}")
                for entry in scan_results:
                    if entry["bundle_path"] not in seen_paths:
                        seen_paths.add(entry["bundle_path"])
                        results.append(entry)
            if not results:
                self.diag.emit("\n".join(log) or "(no game dirs to scan)")
            self.done.emit(results)
        except Exception:
            self.diag.emit(traceback.format_exc())
            self.done.emit([])


class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsManager):
        super().__init__()
        self._settings = settings
        self._cache_mgr: CacheManager | None = None
        self._scan_results: list = []
        # Keyed by bundle_path (unique across both games)
        self._char_map: dict = {}
        self._current_bundle_data: BundleData | None = None
        self._portrait_engine: PortraitEngine | None = None
        self._extraction_worker: ExtractionWorker | None = None
        self._scan_thread: _ScanThread | None = None
        self._build_ui()
        self._restore_state()

    # ---- UI construction ----

    def _build_ui(self):
        self.setWindowTitle("ParanormaSprite")
        self.resize(900, 700)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # Left panel: game folders + character list
        left_panel = QWidget()
        left_panel.setFixedWidth(200)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)

        left_layout.addWidget(QLabel("Game Folders"))
        self._dirs_list = QListWidget()
        self._dirs_list.setFixedHeight(80)
        left_layout.addWidget(self._dirs_list)

        dirs_btns = QHBoxLayout()
        add_btn = QPushButton("Add…")
        add_btn.clicked.connect(self._add_game_dir)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.clicked.connect(self._remove_game_dir)
        dirs_btns.addWidget(add_btn)
        dirs_btns.addWidget(self._remove_btn)
        left_layout.addLayout(dirs_btns)

        chars_header = QHBoxLayout()
        chars_header.addWidget(QLabel("Characters"))
        scan_btn = QPushButton("Scan")
        scan_btn.setFixedWidth(48)
        scan_btn.clicked.connect(self._scan_characters)
        chars_header.addWidget(scan_btn)
        left_layout.addLayout(chars_header)
        self._char_list = QListWidget()
        self._char_list.currentItemChanged.connect(self._on_char_item_changed)
        left_layout.addWidget(self._char_list)

        # Right panel: controls + preview
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        self._controls = ControlPanel()
        self._controls.selection_changed.connect(self._on_selection_changed)
        self._preview = PreviewWidget()

        save_btn = QPushButton("Save Portrait")
        save_btn.clicked.connect(self._save_portrait)

        right_top = QWidget()
        right_top_layout = QVBoxLayout(right_top)
        right_top_layout.setContentsMargins(0, 0, 0, 0)
        right_top_layout.addWidget(self._controls)
        right_top_layout.addWidget(save_btn)

        right_splitter.addWidget(right_top)
        right_splitter.addWidget(self._preview)
        right_splitter.setStretchFactor(0, 0)
        right_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_splitter, 1)

    # ---- startup ----

    def _restore_state(self):
        geom = self._settings.load_geometry()
        if geom:
            self.restoreGeometry(geom)

        self._settings.cache_dir = _DEFAULT_CACHE
        self._init_cache_mgr()

        saved    = self._settings.game_dirs
        detected = self._auto_detect_game_dirs()
        merged   = list(saved)
        for d in detected:
            if d not in merged:
                merged.append(d)
        if merged != saved:
            self._settings.game_dirs = merged

        self._refresh_dirs_list()

        if merged:
            self._scan_characters()
        else:
            QMessageBox.information(
                self, "No game found",
                "ParanormaSprite could not find a PARANORMASIGHT installation.\n\n"
                "Use the Add… button to locate your game's installation folder.",
            )

    def _auto_detect_game_dirs(self) -> list:
        return [p for p in _STEAM_GAME_PATHS if os.path.isdir(p)]

    def _init_cache_mgr(self) -> bool:
        cache_dir = self._settings.cache_dir
        if not cache_dir:
            return False
        os.makedirs(cache_dir, exist_ok=True)
        self._cache_mgr = CacheManager(cache_dir)
        if self._portrait_engine is None:
            self._portrait_engine = PortraitEngine(cache_dir)
        return True

    def _sprites_dir_for(self, entry: dict) -> str:
        """Return the sprites root for a character: {cache_dir}/{game_key}/"""
        return os.path.join(self._settings.cache_dir, entry.get("game_key", ""))

    # ---- game dirs panel ----

    def _refresh_dirs_list(self):
        self._dirs_list.clear()
        for d in self._settings.game_dirs:
            self._dirs_list.addItem(d)

    def _add_game_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Game Installation Folder", "")
        if d:
            dirs = self._settings.game_dirs
            if d not in dirs:
                dirs.append(d)
                self._settings.game_dirs = dirs
            self._refresh_dirs_list()
            self._scan_characters()

    def _remove_game_dir(self):
        item = self._dirs_list.currentItem()
        if item is None:
            return
        d = item.text()
        dirs = self._settings.game_dirs
        if d in dirs:
            dirs.remove(d)
            self._settings.game_dirs = dirs
        self._refresh_dirs_list()
        self._scan_characters()

    # ---- scanning ----

    def _scan_characters(self):
        game_dirs = self._settings.game_dirs
        if not game_dirs:
            self._char_list.clear()
            return
        self._char_list.clear()
        self._char_list.addItem("Scanning…")
        self._scan_thread = _ScanThread(game_dirs, self)
        self._scan_thread.done.connect(self._on_scan_done)
        self._scan_thread.diag.connect(self._on_scan_diag)
        self._scan_thread.start()

    def _on_scan_diag(self, msg: str):
        QMessageBox.warning(self, "Scan — no characters found", msg)

    def _on_scan_done(self, results: list):
        self._scan_results = results
        self._char_map = {r["bundle_path"]: r for r in results}
        self._char_list.clear()
        for entry in results:
            cached = (self._cache_mgr is not None
                      and self._cache_mgr.is_extracted(
                          entry["bundle_path"], entry["char_code"], entry["game_key"]))
            label = ("✓ " if cached else "  ") + entry["display_name"]
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry["bundle_path"])
            self._char_list.addItem(item)

    # ---- character selection / extraction ----

    def _on_char_item_changed(self, current, previous):
        if current is None:
            return
        bundle_path = current.data(Qt.ItemDataRole.UserRole)
        if bundle_path:
            self._on_character_selected(bundle_path)

    def _on_character_selected(self, bundle_path: str):
        entry = self._char_map.get(bundle_path)
        if entry is None:
            return

        if not self._cache_mgr:
            self._init_cache_mgr()

        char_code = entry["char_code"]
        game_key  = entry["game_key"]

        if self._cache_mgr and self._cache_mgr.is_extracted(bundle_path, char_code, game_key):
            self._load_bundle_data(bundle_path, entry)
        else:
            self._run_extraction(bundle_path, entry)

    def _run_extraction(self, bundle_path: str, entry: dict):
        display_name = entry["display_name"]
        char_code    = entry["char_code"]
        game_key     = entry["game_key"]

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Extracting {display_name}…")
        dlg.setModal(True)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(f"Extracting sprites for '{display_name}'…"))
        bar = QProgressBar()
        bar.setRange(0, 0)
        v.addWidget(bar)
        dlg.resize(340, 100)

        worker = ExtractionWorker(
            bundle_path, char_code, game_key,
            self._settings.cache_dir, self._cache_mgr, self)
        self._extraction_worker = worker

        def on_finished(_char_code):
            dlg.accept()
            self._refresh_char_item(bundle_path)
            self._load_bundle_data(bundle_path, entry)

        def on_error(_char_code, msg):
            dlg.accept()
            QMessageBox.critical(self, "Extraction Error",
                                 f"Failed to extract '{display_name}':\n{msg}")

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.start()
        dlg.exec()

    def _refresh_char_item(self, bundle_path: str):
        entry = self._char_map.get(bundle_path)
        if entry is None:
            return
        for i in range(self._char_list.count()):
            item = self._char_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == bundle_path:
                cached = self._cache_mgr.is_extracted(
                    bundle_path, entry["char_code"], entry["game_key"])
                label = ("✓ " if cached else "  ") + entry["display_name"]
                item.setText(label)
                break

    # ---- bundle data + preview ----

    def _load_bundle_data(self, bundle_path: str, entry: dict):
        sprites_dir = self._sprites_dir_for(entry)
        if self._portrait_engine:
            self._portrait_engine.set_sprites_dir(sprites_dir)
            self._portrait_engine.clear_cache()
        try:
            bd = BundleData(bundle_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load bundle data:\n{e}")
            return
        self._current_bundle_data = bd
        self._controls.load_character(bd)

    def _on_selection_changed(self):
        if self._current_bundle_data is None or self._portrait_engine is None:
            return
        sel  = self._controls.current_selection()
        body = sel["body"]
        bi   = self._current_bundle_data.get_body(body)
        if bi is None:
            return
        layers = self._portrait_engine.build_layers(
            body, bi,
            sel["core"],
            sel["eye_base"],   sel["eye_frame"],
            sel["mouth_base"], sel["mouth_frame"],
            sel["use_rev"], sel["use_extra"], sel["use_blush"],
        )
        pixmap = self._portrait_engine.render(
            layers,
            self._current_bundle_data.sprite_rects,
            bi.canvas_rect,
            self._current_bundle_data.char_code,
            flip=sel["use_rev"],
        )
        self._preview.set_pixmap(pixmap)

    def _build_save_stem(self) -> str:
        """Build a default filename stem matching composite_portraits.py's scheme."""
        if self._current_bundle_data is None:
            return "portrait"
        sel       = self._controls.current_selection()
        char_code = self._current_bundle_data.char_code
        body      = sel["body"]
        core      = sel["core"] or ""
        e_base    = sel["eye_base"]
        e_frame   = sel["eye_frame"]
        m_base    = sel["mouth_base"]
        m_frame   = sel["mouth_frame"]

        if e_base and e_frame and m_base and m_frame:
            e_u    = expr_unique(e_base, core)
            m_u    = expr_unique(m_base, core)
            e_part = f"e_{e_u}_{e_frame}" if e_u else f"e_{e_frame}"
            m_part = f"m_{m_u}_{m_frame}" if m_u else f"m_{m_frame}"
            if core == body:
                stem = f"{body}_{e_part}_{m_part}"
            else:
                stem = f"{body}_{core}_{e_part}_{m_part}"
        elif m_base and m_frame:
            m_u    = expr_unique(m_base, core)
            m_part = f"m_{m_u}_{m_frame}" if m_u else f"m_{m_frame}"
            stem   = f"{body}_{m_part}" if core == body else f"{body}_{core}_{m_part}"
        else:
            stem = body

        suffixes = []
        if sel["use_rev"]:   suffixes.append("rev")
        if sel["use_extra"]: suffixes.append("extra")
        if sel["use_blush"]: suffixes.append("blush")
        if suffixes:
            stem = stem + "_" + "_".join(suffixes)

        return f"{char_code}_{stem}"

    def _save_portrait(self):
        pixmap = self._preview.current_pixmap()
        if pixmap is None or pixmap.isNull():
            QMessageBox.information(self, "Save", "No portrait to save.")
            return
        default = self._build_save_stem() + ".png"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Portrait", default, "PNG Images (*.png)")
        if path:
            pixmap.save(path, "PNG")

    def closeEvent(self, event):
        self._settings.save_geometry(self.saveGeometry().data())
        super().closeEvent(event)
