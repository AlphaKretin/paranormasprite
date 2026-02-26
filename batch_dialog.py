"""
batch_dialog.py
---------------
Batch-export dialog: lets the user select characters / bodies / expressions via
a checkbox tree, configure Rev/Extra/Blush variants, and export all combinations
to a chosen output folder.
"""

import itertools
import os

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from bundle_data import BundleData, build_stem
from portrait_engine import PortraitEngine

_USER_ROLE = Qt.ItemDataRole.UserRole
_CHECKED   = Qt.CheckState.Checked
_UNCHECKED = Qt.CheckState.Unchecked
_PARTIAL   = Qt.CheckState.PartiallyChecked
_FLAG_KEYS = ("rev", "extra", "blush")


# ---------------------------------------------------------------------------
# Background loader
# ---------------------------------------------------------------------------

class _BundleLoadThread(QThread):
    progress   = Signal(int, int)   # current, total
    all_loaded = Signal(dict)       # {bundle_path: BundleData}

    def __init__(self, entries: list, parent=None):
        super().__init__(parent)
        self._entries = entries  # list of scan-result dicts (extracted chars only)

    def run(self):
        result = {}
        total = len(self._entries)
        for i, entry in enumerate(self._entries):
            self.progress.emit(i, total)
            try:
                bd = BundleData(entry["bundle_path"])
                result[entry["bundle_path"]] = bd
            except Exception:
                pass
        self.progress.emit(total, total)
        self.all_loaded.emit(result)


# ---------------------------------------------------------------------------
# Export worker
# ---------------------------------------------------------------------------

class _ExportWorker(QThread):
    progress = Signal(int, int, str)  # current, total, filename
    finished = Signal()
    error    = Signal(str)

    def __init__(self, tasks: list, parent=None):
        super().__init__(parent)
        self._tasks = tasks

    def run(self):
        engine = PortraitEngine("")
        current_sprites_dir = None
        total = len(self._tasks)
        try:
            for i, task in enumerate(self._tasks):
                if task["sprites_dir"] != current_sprites_dir:
                    engine.set_sprites_dir(task["sprites_dir"])
                    engine.clear_cache()
                    current_sprites_dir = task["sprites_dir"]

                layers = engine.build_layers(
                    task["body"], task["bi"], task["core"],
                    task["e_base"], task["e_frame"],
                    task["m_base"], task["m_frame"],
                    task["use_rev"], task["use_extra"], task["use_blush"],
                )
                img = engine.render_pil(
                    layers, task["sprite_rects"], task["canvas_rect"],
                    task["char_code"], flip=task["use_rev"],
                )
                os.makedirs(os.path.dirname(task["out_path"]), exist_ok=True)
                img.save(task["out_path"])
                self.progress.emit(i + 1, total, os.path.basename(task["out_path"]))

            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flag_subsets(flags: dict) -> list:
    """
    flags: {key: QCheckBox}
    Returns all 2^n subsets of the *checked* flags as list of
    {rev: bool, extra: bool, blush: bool} dicts (always includes the base / no-flags case).
    """
    active = [k for k, cb in flags.items() if cb.isChecked()]
    results = []
    for r in range(len(active) + 1):
        for combo in itertools.combinations(active, r):
            combo_set = set(combo)
            results.append({k: (k in combo_set) for k in _FLAG_KEYS})
    return results


def _combo_count(eyes: list, mouths: list) -> int:
    return max(len(eyes), 1) * max(len(mouths), 1)


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class BatchExportDialog(QDialog):
    def __init__(self, char_map: dict, cache_mgr, cache_dir: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Export")
        self.resize(700, 560)

        self._char_map  = char_map
        self._cache_mgr = cache_mgr
        self._cache_dir = cache_dir

        # State
        self._bundle_data:      dict = {}  # bundle_path → BundleData
        self._body_flags:       dict = {}  # id(body_item) → {key: QCheckBox}
        self._body_sprite_sizes:dict = {}  # id(body_item) → int (bytes of body PNG)
        self._char_items:       list = []  # top-level QTreeWidgetItems
        self._updating = False
        self._load_thread:   _BundleLoadThread | None = None
        self._export_worker: _ExportWorker | None = None

        self._build_ui()
        self._start_loading()

    # ---- UI construction ----

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Loading state
        self._load_label = QLabel("Loading character data…")
        self._load_bar   = QProgressBar()
        self._load_bar.setRange(0, 0)
        root.addWidget(self._load_label)
        root.addWidget(self._load_bar)

        # Select / Unselect All row (hidden while loading)
        self._sel_row = QWidget()
        sel_hl = QHBoxLayout(self._sel_row)
        sel_hl.setContentsMargins(0, 0, 0, 0)
        sel_hl.setSpacing(4)
        sel_all_btn = QPushButton("Select All")
        sel_all_btn.clicked.connect(self._select_all)
        unsel_all_btn = QPushButton("Unselect All")
        unsel_all_btn.clicked.connect(self._unselect_all)
        sel_hl.addWidget(sel_all_btn)
        sel_hl.addWidget(unsel_all_btn)
        sel_hl.addStretch()
        self._sel_row.setVisible(False)
        root.addWidget(self._sel_row)

        # Tree (hidden while loading)
        self._tree = QTreeWidget()
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Character / Body / Expression", "Variants"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._tree.header().resizeSection(1, 180)
        self._tree.setVisible(False)
        self._tree.itemChanged.connect(self._on_item_changed)
        root.addWidget(self._tree, 1)

        # Output folder row
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Output folder:"))
        self._out_edit = QLineEdit()
        self._out_edit.setReadOnly(True)
        self._out_edit.setPlaceholderText("(choose a folder)")
        folder_row.addWidget(self._out_edit, 1)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_output)
        folder_row.addWidget(browse_btn)
        root.addLayout(folder_row)

        # Count label
        self._count_label = QLabel("0 images")
        root.addWidget(self._count_label)

        # Export progress (hidden initially)
        self._export_bar    = QProgressBar()
        self._export_status = QLabel("")
        self._export_bar.setVisible(False)
        self._export_status.setVisible(False)
        root.addWidget(self._export_bar)
        root.addWidget(self._export_status)

        # Buttons
        btn_row = QHBoxLayout()
        self._export_btn = QPushButton("Export")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._start_export)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(self._export_btn)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    # ---- Loading phase ----

    def _start_loading(self):
        extracted = [
            entry for entry in self._char_map.values()
            if self._cache_mgr and self._cache_mgr.is_extracted(
                entry["bundle_path"], entry["char_code"], entry["game_key"])
        ]
        if not extracted:
            self._load_label.setText("No extracted characters found. Open characters in the viewer first.")
            self._load_bar.setVisible(False)
            return

        self._load_thread = _BundleLoadThread(extracted, self)
        self._load_thread.progress.connect(self._on_load_progress)
        self._load_thread.all_loaded.connect(self._on_all_loaded)
        self._load_thread.start()

    def _on_load_progress(self, current: int, total: int):
        if self._load_bar.maximum() == 0:
            self._load_bar.setRange(0, total)
        self._load_bar.setValue(current)

    def _on_all_loaded(self, bundle_data: dict):
        self._bundle_data = bundle_data
        self._load_label.setVisible(False)
        self._load_bar.setVisible(False)
        self._sel_row.setVisible(True)
        self._tree.setVisible(True)
        self._populate_tree()

    # ---- Tree population ----

    def _populate_tree(self):
        self._tree.blockSignals(True)
        self._tree.clear()
        self._char_items.clear()
        self._body_flags.clear()
        self._body_sprite_sizes.clear()

        for bundle_path, bd in self._bundle_data.items():
            entry = self._char_map.get(bundle_path)
            if entry is None:
                continue

            char_item = QTreeWidgetItem(self._tree)
            char_item.setText(0, entry["display_name"])
            char_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled |
                Qt.ItemFlag.ItemIsAutoTristate
            )
            char_item.setCheckState(0, _UNCHECKED)
            char_item.setData(0, _USER_ROLE, {
                "bundle_path": bundle_path,
                "char_code":   entry["char_code"],
                "game_key":    entry["game_key"],
            })
            self._char_items.append(char_item)

            for bi in bd.bodies:
                body_item = QTreeWidgetItem(char_item)
                body_item.setText(0, bi.name)
                body_item.setFlags(
                    Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled |
                    Qt.ItemFlag.ItemIsAutoTristate
                )
                body_item.setCheckState(0, _UNCHECKED)
                body_item.setData(0, _USER_ROLE, {"body": bi.name})

                # Body sprite size for estimate
                sprites_dir = os.path.join(self._cache_dir, entry["game_key"])
                body_png    = os.path.join(sprites_dir, entry["char_code"], bi.name + ".png")
                try:
                    self._body_sprite_sizes[id(body_item)] = os.path.getsize(body_png)
                except OSError:
                    self._body_sprite_sizes[id(body_item)] = 0

                # Variant flags widget in column 1
                flag_widget, flag_cbs = self._make_flag_widget(bi)
                self._body_flags[id(body_item)] = flag_cbs
                self._tree.setItemWidget(body_item, 1, flag_widget)

                cores = bd.available_cores(bi.name)
                for core in cores:
                    eyes   = bd.available_eye_frames(bi.name, core)
                    mouths = bd.available_mouth_frames(bi.name, core)
                    count  = _combo_count(eyes, mouths)

                    core_item = QTreeWidgetItem(body_item)
                    core_item.setText(0, f"{core}  ({count}×)")
                    core_item.setFlags(
                        Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
                    )
                    core_item.setCheckState(0, _UNCHECKED)
                    core_item.setData(0, _USER_ROLE, {
                        "bundle_path": bundle_path,
                        "body":        bi.name,
                        "core":        core,
                        "combo_count": count,
                    })

        self._tree.blockSignals(False)

    def _make_flag_widget(self, bi) -> tuple:
        """Return (widget, {key: QCheckBox}) for the Rev/Extra/Blush flags."""
        w  = QWidget()
        hl = QHBoxLayout(w)
        hl.setContentsMargins(4, 0, 4, 0)
        hl.setSpacing(6)
        cbs = {}
        specs = [("rev", "Rev", bi.has_rev),
                 ("extra", "Extra", bi.has_extras),
                 ("blush", "Blush", bi.has_blush)]
        for key, label, available in specs:
            cb = QCheckBox(label)
            cb.setEnabled(available)
            cb.stateChanged.connect(self._update_count)
            hl.addWidget(cb)
            cbs[key] = cb
        hl.addStretch()
        return w, cbs

    # ---- Checkbox cascade ----

    def _on_item_changed(self, item: QTreeWidgetItem, col: int):
        if col != 0 or self._updating:
            return
        self._updating = True
        state = item.checkState(0)
        if state != _PARTIAL:
            self._cascade_down(item, state)
        self._update_ancestors(item.parent())
        self._updating = False
        self._update_count()

    def _cascade_down(self, item: QTreeWidgetItem, state: Qt.CheckState):
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, state)
            self._cascade_down(child, state)

    def _update_ancestors(self, item: QTreeWidgetItem | None):
        while item is not None:
            n_checked = sum(
                1 for i in range(item.childCount())
                if item.child(i).checkState(0) == _CHECKED
            )
            n_partial = sum(
                1 for i in range(item.childCount())
                if item.child(i).checkState(0) == _PARTIAL
            )
            n_total = item.childCount()
            if n_checked == n_total:
                item.setCheckState(0, _CHECKED)
            elif n_checked == 0 and n_partial == 0:
                item.setCheckState(0, _UNCHECKED)
            else:
                item.setCheckState(0, _PARTIAL)
            item = item.parent()

    # ---- Count / estimate ----

    def _update_count(self):
        total_count = 0
        total_bytes = 0
        for char_item in self._char_items:
            for b in range(char_item.childCount()):
                body_item  = char_item.child(b)
                flags      = self._body_flags.get(id(body_item), {})
                n_flags    = sum(1 for cb in flags.values() if cb.isEnabled() and cb.isChecked())
                multiplier = 2 ** n_flags
                body_bytes = self._body_sprite_sizes.get(id(body_item), 0)
                for c in range(body_item.childCount()):
                    core_item = body_item.child(c)
                    if core_item.checkState(0) == _CHECKED:
                        combo_count = core_item.data(0, _USER_ROLE)["combo_count"]
                        total_count += combo_count * multiplier
                        total_bytes += combo_count * multiplier * body_bytes

        if total_bytes >= 1024 ** 3:
            size_str = f"~{total_bytes / 1024 ** 3:.2f} GB"
        elif total_bytes >= 1024 ** 2:
            size_str = f"~{total_bytes / 1024 ** 2:.1f} MB"
        elif total_bytes > 0:
            size_str = f"~{total_bytes / 1024:.0f} KB"
        else:
            size_str = "size unknown"
        self._count_label.setText(
            f"{total_count} image{'s' if total_count != 1 else ''}  ({size_str} estimated)"
        )
        self._export_btn.setEnabled(total_count > 0 and bool(self._out_edit.text()))

    def _select_all(self):
        self._set_all_checked(_CHECKED)

    def _unselect_all(self):
        self._set_all_checked(_UNCHECKED)

    def _set_all_checked(self, state: Qt.CheckState):
        checked = (state == _CHECKED)
        self._updating = True
        for char_item in self._char_items:
            char_item.setCheckState(0, state)
            self._cascade_down(char_item, state)
            for b in range(char_item.childCount()):
                body_item = char_item.child(b)
                for cb in self._body_flags.get(id(body_item), {}).values():
                    if cb.isEnabled():
                        cb.blockSignals(True)
                        cb.setChecked(checked)
                        cb.blockSignals(False)
        self._updating = False
        self._update_count()

    # ---- Output folder ----

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Folder", "")
        if d:
            self._out_edit.setText(d)
            self._update_count()

    # ---- Export ----

    def _collect_tasks(self) -> list:
        out_dir = self._out_edit.text()
        tasks   = []

        for char_item in self._char_items:
            char_data    = char_item.data(0, _USER_ROLE)
            bundle_path  = char_data["bundle_path"]
            char_code    = char_data["char_code"]
            game_key     = char_data["game_key"]
            sprites_dir  = os.path.join(self._cache_dir, game_key)
            bd           = self._bundle_data.get(bundle_path)
            if bd is None:
                continue

            for b in range(char_item.childCount()):
                body_item = char_item.child(b)
                body      = body_item.data(0, _USER_ROLE)["body"]
                bi        = bd.get_body(body)
                if bi is None:
                    continue
                flags      = self._body_flags.get(id(body_item), {})
                flag_sets  = _flag_subsets(flags)

                for c in range(body_item.childCount()):
                    core_item = body_item.child(c)
                    if core_item.checkState(0) != _CHECKED:
                        continue
                    core_data = core_item.data(0, _USER_ROLE)
                    core      = core_data["core"]

                    eyes   = bd.available_eye_frames(body, core) or [(None, None)]
                    mouths = bd.available_mouth_frames(body, core) or [(None, None)]

                    for e_base, e_frame in eyes:
                        for m_base, m_frame in mouths:
                            for flag_set in flag_sets:
                                stem     = build_stem(
                                    char_code, body, core,
                                    e_base, e_frame, m_base, m_frame,
                                    use_rev=flag_set["rev"],
                                    use_extra=flag_set["extra"],
                                    use_blush=flag_set["blush"],
                                )
                                out_path = os.path.join(out_dir, char_code, stem + ".png")
                                tasks.append({
                                    "sprites_dir":  sprites_dir,
                                    "char_code":    char_code,
                                    "sprite_rects": bd.sprite_rects,
                                    "canvas_rect":  bi.canvas_rect,
                                    "body":         body,
                                    "bi":           bi,
                                    "core":         core,
                                    "e_base":       e_base,
                                    "e_frame":      e_frame,
                                    "m_base":       m_base,
                                    "m_frame":      m_frame,
                                    "use_rev":      flag_set["rev"],
                                    "use_extra":    flag_set["extra"],
                                    "use_blush":    flag_set["blush"],
                                    "out_path":     out_path,
                                })
        return tasks

    def _start_export(self):
        tasks = self._collect_tasks()
        if not tasks:
            QMessageBox.information(self, "Batch Export", "No images selected.")
            return

        self._export_bar.setRange(0, len(tasks))
        self._export_bar.setValue(0)
        self._export_bar.setVisible(True)
        self._export_status.setVisible(True)
        self._export_status.setText("Starting…")
        self._export_btn.setEnabled(False)

        self._export_worker = _ExportWorker(tasks, self)
        self._export_worker.progress.connect(self._on_export_progress)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.error.connect(self._on_export_error)
        self._export_worker.start()

    def _on_export_progress(self, current: int, total: int, filename: str):
        self._export_bar.setValue(current)
        self._export_status.setText(f"{current}/{total}  {filename}")

    def _on_export_finished(self):
        self._export_status.setText(
            f"Done — exported to {self._out_edit.text()}"
        )
        self._export_btn.setEnabled(True)

    def _on_export_error(self, msg: str):
        self._export_bar.setVisible(False)
        self._export_status.setVisible(False)
        self._export_btn.setEnabled(True)
        QMessageBox.critical(self, "Export Error", msg)
