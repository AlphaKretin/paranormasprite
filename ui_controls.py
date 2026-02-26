from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QComboBox, QCheckBox, QLabel, QHBoxLayout,
)


class ControlPanel(QWidget):
    selection_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bundle_data = None
        self._updating = False
        self._build_ui()

    def _build_ui(self):
        layout = QFormLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._body_combo  = QComboBox()
        self._core_combo  = QComboBox()
        self._eye_combo   = QComboBox()
        self._mouth_combo = QComboBox()

        self._rev_check   = QCheckBox("Reversed")
        self._extra_check = QCheckBox("Extra")
        self._blush_check = QCheckBox("Blush")

        self._body_label  = QLabel("Body:")
        self._core_label  = QLabel("Expression:")
        self._eye_label   = QLabel("Eye frame:")
        self._mouth_label = QLabel("Mth frame:")

        layout.addRow(self._body_label,  self._body_combo)
        layout.addRow(self._core_label,  self._core_combo)
        layout.addRow(self._eye_label,   self._eye_combo)
        layout.addRow(self._mouth_label, self._mouth_combo)

        check_row = QWidget()
        hr = QHBoxLayout(check_row)
        hr.setContentsMargins(0, 0, 0, 0)
        hr.addWidget(self._rev_check)
        hr.addWidget(self._extra_check)
        hr.addWidget(self._blush_check)
        layout.addRow("", check_row)

        self._body_combo.currentIndexChanged.connect(self._on_body_changed)
        self._core_combo.currentIndexChanged.connect(self._on_core_changed)
        self._eye_combo.currentIndexChanged.connect(self._emit_changed)
        self._mouth_combo.currentIndexChanged.connect(self._emit_changed)
        self._rev_check.stateChanged.connect(self._emit_changed)
        self._extra_check.stateChanged.connect(self._emit_changed)
        self._blush_check.stateChanged.connect(self._emit_changed)

    # ---- public API ----

    def load_character(self, bundle_data):
        self._bundle_data = bundle_data
        self._updating = True
        self._body_combo.clear()
        if bundle_data:
            for bi in bundle_data.bodies:
                self._body_combo.addItem(bi.name)
        self._updating = False
        self._on_body_changed()

    def current_selection(self) -> dict:
        eye_data   = self._eye_combo.currentData()
        mouth_data = self._mouth_combo.currentData()
        return {
            "body":       self._body_combo.currentText(),
            "core":       self._core_combo.currentText(),
            "eye_base":   eye_data[0]   if eye_data   else None,
            "eye_frame":  eye_data[1]   if eye_data   else None,
            "mouth_base": mouth_data[0] if mouth_data else None,
            "mouth_frame":mouth_data[1] if mouth_data else None,
            "use_rev":    self._rev_check.isChecked(),
            "use_extra":  self._extra_check.isChecked(),
            "use_blush":  self._blush_check.isChecked(),
        }

    # ---- cascade ----

    def _on_body_changed(self):
        if self._updating:
            return
        self._updating = True

        body_name = self._body_combo.currentText()
        bi = self._bundle_data.get_body(body_name) if self._bundle_data else None

        self._core_combo.clear()
        if bi:
            cores = self._bundle_data.available_cores(body_name)
            for c in cores:
                self._core_combo.addItem(c)
            self._core_label.setVisible(bool(cores))
            self._core_combo.setVisible(bool(cores))
        else:
            self._core_label.setVisible(False)
            self._core_combo.setVisible(False)

        if bi:
            self._rev_check.setEnabled(bi.has_rev)
            self._extra_check.setEnabled(bi.has_extras)
            self._blush_check.setEnabled(bi.has_blush)
        else:
            self._rev_check.setEnabled(False)
            self._extra_check.setEnabled(False)
            self._blush_check.setEnabled(False)

        self._updating = False
        self._on_core_changed()

    def _on_core_changed(self):
        if self._updating:
            return
        self._updating = True

        body_name = self._body_combo.currentText()
        core      = self._core_combo.currentText()
        bd        = self._bundle_data

        self._eye_combo.clear()
        self._mouth_combo.clear()

        if bd and body_name and core:
            eye_frames = bd.available_eye_frames(body_name, core)
            if eye_frames:
                self._eye_combo.addItem("(none)", None)
                for e_base, frame in eye_frames:
                    self._eye_combo.addItem(f"{e_base}_{frame}", (e_base, frame))
            self._eye_label.setVisible(bool(eye_frames))
            self._eye_combo.setVisible(bool(eye_frames))

            mouth_frames = bd.available_mouth_frames(body_name, core)
            if mouth_frames:
                self._mouth_combo.addItem("(none)", None)
                for m_base, frame in mouth_frames:
                    self._mouth_combo.addItem(f"{m_base}_{frame}", (m_base, frame))
            self._mouth_label.setVisible(bool(mouth_frames))
            self._mouth_combo.setVisible(bool(mouth_frames))
        else:
            self._eye_label.setVisible(False)
            self._eye_combo.setVisible(False)
            self._mouth_label.setVisible(False)
            self._mouth_combo.setVisible(False)

        self._updating = False
        self._emit_changed()

    def _emit_changed(self, *_):
        if not self._updating:
            self.selection_changed.emit()
