from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel


class PreviewWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(200, 200)

    def set_pixmap(self, pixmap: QPixmap):
        self._full_pixmap = pixmap
        self._update_scaled()

    def current_pixmap(self) -> QPixmap | None:
        return self._full_pixmap

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled()

    def _update_scaled(self):
        if self._full_pixmap is None or self._full_pixmap.isNull():
            return
        scaled = self._full_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        super().setPixmap(scaled)
