"""Point d'entrée de l'application HEIC -> PNG.

Lancement : ``python main.py`` depuis le dossier ``heic2png``.
"""

from __future__ import annotations

import multiprocessing
import sys

from PySide6.QtWidgets import QApplication

from heic2png.ui.main_window import MainWindow


def main() -> int:
    # Nécessaire pour ProcessPoolExecutor sous Windows / macOS (spawn).
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    app.setApplicationName("HEIC → PNG")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
