"""Point d'entrée de l'application HEIC -> PNG.

Lancement : ``python main.py`` depuis le dossier ``heic2png``.
"""

from __future__ import annotations

import logging
import pathlib
import sys

from PySide6.QtWidgets import QApplication

from heic2png.ui.main_window import MainWindow


def _setup_logging() -> pathlib.Path:
    log_dir = pathlib.Path.home() / ".local" / "share" / "heic2png"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "debug.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return log_path


def main() -> int:
    log_path = _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Démarrage — journal : %s", log_path)

    app = QApplication(sys.argv)
    app.setApplicationName("HEIC → PNG")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
