import sys

from PySide6.QtWidgets import QApplication

from settings import SettingsManager
from main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ParanormaSprite")
    app.setOrganizationName("paranormasprite")

    settings = SettingsManager()
    window = MainWindow(settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
