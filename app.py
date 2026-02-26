import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from settings import SettingsManager
from main_window import MainWindow


def _resource(relative: str) -> str:
    """Resolve a bundled resource path for both dev and PyInstaller one-file mode."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ParanormaSprite")
    app.setOrganizationName("paranormasprite")

    icon_path = _resource("icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    settings = SettingsManager()
    window = MainWindow(settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
