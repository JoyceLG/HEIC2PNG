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

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def paths(self) -> set[str]:
        return {item.path for item in self.items}

    def add(self, path: str) -> PhotoItem | None:
        """Ajoute une photo si elle n'est pas déjà présente."""
        normalized = os.path.abspath(path)
        if normalized in {os.path.abspath(p) for p in self.paths()}:
            return None
        item = PhotoItem(path=normalized)
        self.items.append(item)
        return item

    def remove(self, paths: set[str]) -> None:
        self.items = [item for item in self.items if item.path not in paths]

    def clear(self) -> None:
        self.items.clear()

    def get(self, path: str) -> PhotoItem | None:
        for item in self.items:
            if item.path == path:
                return item
        return None
