"""Zone de dépôt acceptant le glisser-déposer de fichiers et dossiers HEIC."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QLabel

from ..converter import HEIC_EXTENSIONS, is_heic


class DropZone(QLabel):
    """Étiquette interactive servant de cible pour le glisser-déposer."""

    files_dropped = Signal(list)  # liste de chemins HEIC

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setText(
            "Glissez-déposez ici vos photos HEIC ou des dossiers\n\n"
            "ou utilisez les boutons « Ajouter des photos » / « Ajouter un dossier »"
        )
        self.setObjectName("dropZone")
        self.setMinimumHeight(90)
        self._set_style(False)

    def _set_style(self, active: bool) -> None:
        border = "#1a73e8" if active else "#9aa0a6"
        background = "#e8f0fe" if active else "#fafafa"
        self.setStyleSheet(
            f"#dropZone {{ border: 2px dashed {border}; border-radius: 8px;"
            f" background: {background}; color: #5f6368; padding: 12px; }}"
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_style(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._set_style(False)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        self._set_style(False)
        paths: list[str] = []
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if not local:
                continue
            if os.path.isdir(local):
                paths.extend(_scan_dir(local))
            elif is_heic(local):
                paths.append(local)
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


def _scan_dir(folder: str) -> list[str]:
    """Renvoie tous les fichiers HEIC contenus récursivement dans un dossier."""
    found: list[str] = []
    for root, _dirs, files in os.walk(folder):
        for name in files:
            if os.path.splitext(name)[1].lower() in HEIC_EXTENSIONS:
                found.append(os.path.join(root, name))
    return found
