"""Vues d'affichage des photos : liste détaillée et cartes avec tri."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from PIL import Image
from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .photo_model import PhotoItem, PhotoStore, PhotoStatus

THUMB_SIZE = 160


def _load_thumbnail(path: str, size: int = THUMB_SIZE) -> tuple[str, QImage | None]:
    """Génère une vignette QImage depuis le fichier source (thread d'E/S)."""
    try:
        with Image.open(path) as img:
            img = img.convert("RGBA")
            img.thumbnail((size, size))
            data = img.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
            return path, qimg.copy()
    except Exception:  # noqa: BLE001 - vignette best effort
        return path, None


class ThumbnailLoader(QObject):
    """Charge les vignettes en arrière-plan et les renvoie au thread GUI."""

    ready = Signal(str, object)  # chemin, QImage
    finished = Signal()

    def __init__(self, paths: list[str], max_workers: int = 4) -> None:
        super().__init__()
        self._paths = paths
        self._max_workers = max_workers
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                for path, qimg in pool.map(_load_thumbnail, self._paths):
                    if self._cancelled:
                        break
                    if qimg is not None:
                        self.ready.emit(path, qimg)
        finally:
            self.finished.emit()


# Critères de tri : libellé -> clé de tri appliquée à un PhotoItem.
SORT_KEYS = {
    "Nom (A→Z)": (lambda i: i.name.lower(), False),
    "Nom (Z→A)": (lambda i: i.name.lower(), True),
    "Date (récent→ancien)": (lambda i: i.created or "", True),
    "Date (ancien→récent)": (lambda i: i.created or "", False),
    "Taille (grand→petit)": (lambda i: i.size, True),
    "Taille (petit→grand)": (lambda i: i.size, False),
    "Statut": (lambda i: i.status.value, False),
}


class PhotoGallery(QWidget):
    """Widget combinant vue liste et vue cartes, avec tri et sélection."""

    selection_changed = Signal(object)  # PhotoItem | None

    def __init__(self, store: PhotoStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._thumbnails: dict[str, QPixmap] = {}
        self._build_ui()

    # ----- Construction de l'interface ---------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Affichage :"))
        self.view_combo = QComboBox()
        self.view_combo.addItems(["Liste", "Cartes"])
        self.view_combo.currentIndexChanged.connect(self._on_view_changed)
        toolbar.addWidget(self.view_combo)

        toolbar.addSpacing(16)
        toolbar.addWidget(QLabel("Trier par :"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(SORT_KEYS.keys())
        self.sort_combo.currentIndexChanged.connect(self.refresh)
        toolbar.addWidget(self.sort_combo)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.stack = QStackedWidget()
        self.table = self._build_table()
        self.cards = self._build_cards()
        self.stack.addWidget(self.table)
        self.stack.addWidget(self.cards)
        layout.addWidget(self.stack)

    def _build_table(self) -> QTableWidget:
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(
            ["Nom", "Dimensions", "Taille", "Date", "Appareil", "Statut"]
        )
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 6):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        table.itemSelectionChanged.connect(self._on_table_selection)
        return table

    def _build_cards(self) -> QListWidget:
        cards = QListWidget()
        cards.setViewMode(QListWidget.ViewMode.IconMode)
        cards.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        cards.setGridSize(QSize(THUMB_SIZE + 40, THUMB_SIZE + 70))
        cards.setResizeMode(QListWidget.ResizeMode.Adjust)
        cards.setMovement(QListWidget.Movement.Static)
        cards.setSpacing(8)
        cards.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        cards.itemSelectionChanged.connect(self._on_cards_selection)
        return cards

    # ----- Données -----------------------------------------------------
    def _sorted_items(self) -> list[PhotoItem]:
        key, reverse = SORT_KEYS[self.sort_combo.currentText()]
        return sorted(self._store.items, key=key, reverse=reverse)

    def refresh(self) -> None:
        """Reconstruit les deux vues à partir du store."""
        items = self._sorted_items()
        self._fill_table(items)
        self._fill_cards(items)

    def _fill_table(self, items: list[PhotoItem]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            values = [
                item.name,
                item.dimensions,
                item.metadata.file_size_human if item.metadata else "—",
                item.created or "—",
                self._camera_label(item),
                item.status.value,
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, item.path)
                if col == 5:
                    cell.setForeground(QColor(item.status.color))
                self.table.setItem(row, col, cell)
        self.table.blockSignals(False)

    def _fill_cards(self, items: list[PhotoItem]) -> None:
        self.cards.blockSignals(True)
        self.cards.clear()
        for item in items:
            label = (
                f"{item.name}\n{item.dimensions} · "
                f"{item.metadata.file_size_human if item.metadata else '—'}\n"
                f"{item.status.value}"
            )
            entry = QListWidgetItem(label)
            entry.setData(Qt.ItemDataRole.UserRole, item.path)
            entry.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            pixmap = self._thumbnails.get(item.path)
            if pixmap is not None:
                entry.setIcon(QIcon(pixmap))
            entry.setForeground(QColor(item.status.color))
            self.cards.addItem(entry)
        self.cards.blockSignals(False)

    @staticmethod
    def _camera_label(item: PhotoItem) -> str:
        if not item.metadata:
            return "—"
        parts = [p for p in (item.metadata.camera_make, item.metadata.camera_model) if p]
        return " ".join(parts) if parts else "—"

    # ----- Vignettes ---------------------------------------------------
    def set_thumbnail(self, path: str, image: QImage) -> None:
        pixmap = QPixmap.fromImage(image)
        self._thumbnails[path] = pixmap
        for row in range(self.cards.count()):
            entry = self.cards.item(row)
            if entry.data(Qt.ItemDataRole.UserRole) == path:
                entry.setIcon(QIcon(pixmap))
                break

    # ----- Sélection / interactions ------------------------------------
    def _on_view_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)

    def _on_table_selection(self) -> None:
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        if not rows:
            self.selection_changed.emit(None)
            return
        path = self.table.item(min(rows), 0).data(Qt.ItemDataRole.UserRole)
        self.selection_changed.emit(self._store.get(path))

    def _on_cards_selection(self) -> None:
        selected = self.cards.selectedItems()
        if not selected:
            self.selection_changed.emit(None)
            return
        path = selected[0].data(Qt.ItemDataRole.UserRole)
        self.selection_changed.emit(self._store.get(path))

    def selected_paths(self) -> set[str]:
        """Renvoie les chemins sélectionnés dans la vue active."""
        if self.stack.currentIndex() == 0:
            rows = {idx.row() for idx in self.table.selectedIndexes()}
            return {
                self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in rows
            }
        return {
            i.data(Qt.ItemDataRole.UserRole) for i in self.cards.selectedItems()
        }
