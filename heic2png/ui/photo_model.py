"""Modèle de données représentant une photo dans l'interface."""

from __future__ import annotations

import enum
import os
from dataclasses import dataclass, field

from ..converter import PhotoMetadata


class PhotoStatus(enum.Enum):
    """États possibles d'une photo dans la file de conversion."""

    PENDING = "En attente"
    RUNNING = "En cours"
    DONE = "Convertie"
    ERROR = "Erreur"
    SKIPPED = "Ignorée"

    @property
    def color(self) -> str:
        return {
            PhotoStatus.PENDING: "#9aa0a6",
            PhotoStatus.RUNNING: "#1a73e8",
            PhotoStatus.DONE: "#188038",
            PhotoStatus.ERROR: "#d93025",
            PhotoStatus.SKIPPED: "#b06000",
        }[self]


@dataclass
class PhotoItem:
    """Une photo HEIC ajoutée par l'utilisateur."""

    path: str
    metadata: PhotoMetadata | None = None
    status: PhotoStatus = PhotoStatus.PENDING
    output_path: str | None = None
    error: str | None = None
    thumbnail_loaded: bool = False
    exif_loaded: bool = False

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    @property
    def folder(self) -> str:
        return os.path.dirname(self.path)

    @property
    def size(self) -> int:
        return self.metadata.file_size if self.metadata else 0

    @property
    def created(self) -> str:
        return self.metadata.created if self.metadata and self.metadata.created else ""

    @property
    def dimensions(self) -> str:
        return self.metadata.dimensions if self.metadata else "—"


@dataclass
class PhotoStore:
    """Conteneur ordonné de ``PhotoItem`` sans doublon de chemin."""

    items: list[PhotoItem] = field(default_factory=list)
    _by_path: dict[str, PhotoItem] = field(default_factory=dict)

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def paths(self) -> set[str]:
        return set(self._by_path.keys())

    def add(self, path: str) -> PhotoItem | None:
        """Ajoute une photo si elle n'est pas déjà présente (O(1))."""
        normalized = os.path.abspath(path)
        if normalized in self._by_path:
            return None
        item = PhotoItem(path=normalized)
        self.items.append(item)
        self._by_path[normalized] = item
        return item

    def remove(self, paths: set[str]) -> None:
        self.items = [item for item in self.items if item.path not in paths]
        for path in paths:
            self._by_path.pop(path, None)

    def clear(self) -> None:
        self.items.clear()
        self._by_path.clear()

    def get(self, path: str) -> PhotoItem | None:
        return self._by_path.get(path)
