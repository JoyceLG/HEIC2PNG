"""Workers Qt pour l'extraction de métadonnées et la conversion parallèle."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QObject, Signal

from .converter import (
    ConversionResult,
    HEIC_EXTENSIONS,
    PhotoMetadata,
    convert_heic_to_png,
    extract_metadata,
)


def _metadata_job(path: str) -> tuple[str, PhotoMetadata]:
    """Tâche exécutée en thread pour lire les métadonnées d'un fichier."""
    return path, extract_metadata(path)


class FolderScanWorker(QObject):
    """Parcourt récursivement un ou plusieurs dossiers à la recherche de HEIC.

    Émet les chemins trouvés par lots pour un affichage progressif, sans
    bloquer l'interface lors de l'analyse d'arborescences volumineuses.
    """

    found = Signal(list)  # lot de chemins HEIC
    finished = Signal(int)  # nombre total trouvé

    def __init__(self, folders: list[str], batch_size: int = 200) -> None:
        super().__init__()
        self._folders = folders
        self._batch_size = batch_size
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        total = 0
        batch: list[str] = []
        try:
            for folder in self._folders:
                for root, _dirs, files in os.walk(folder):
                    if self._cancelled:
                        return
                    for name in files:
                        if os.path.splitext(name)[1].lower() in HEIC_EXTENSIONS:
                            batch.append(os.path.join(root, name))
                            total += 1
                            if len(batch) >= self._batch_size:
                                self.found.emit(batch)
                                batch = []
            if batch:
                self.found.emit(batch)
        finally:
            self.finished.emit(total)


class MetadataWorker(QObject):
    """Charge les métadonnées des photos en arrière-plan (threads d'E/S)."""

    loaded = Signal(str, object)  # chemin, PhotoMetadata
    progress = Signal(int, int)  # chargés, total
    finished = Signal()

    def __init__(self, paths: list[str], max_workers: int | None = None) -> None:
        super().__init__()
        self._paths = paths
        self._max_workers = max_workers or min(4, max(1, (os.cpu_count() or 4) // 2))
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        total = len(self._paths)
        done = 0
        try:
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                futures = {pool.submit(_metadata_job, p): p for p in self._paths}
                for future in as_completed(futures):
                    if self._cancelled:
                        break
                    try:
                        path, meta = future.result()
                        self.loaded.emit(path, meta)
                    except Exception:  # noqa: BLE001 - best effort
                        pass
                    done += 1
                    self.progress.emit(done, total)
        finally:
            self.finished.emit()


class ConversionWorker(QObject):
    """Convertit les photos HEIC en PNG via un pool de processus."""

    progress = Signal(int, int)  # terminés, total
    item_done = Signal(object)  # ConversionResult
    log = Signal(str)
    finished = Signal(int, int, int)  # succès, échecs, ignorés

    def __init__(
        self,
        paths: list[str],
        output_dir: str | None,
        keep_exif: bool = True,
        overwrite: bool = False,
        max_workers: int | None = None,
    ) -> None:
        super().__init__()
        self._paths = paths
        self._output_dir = output_dir
        self._keep_exif = keep_exif
        self._overwrite = overwrite
        self._max_workers = max_workers or max(1, min(4, (os.cpu_count() or 4) // 2))
        self._cancelled = False
        self._executor: ThreadPoolExecutor | None = None

    def cancel(self) -> None:
        self._cancelled = True
        self.log.emit("Annulation demandée…")
        if self._executor is not None:
            # cancel_futures évite de démarrer les tâches non commencées.
            self._executor.shutdown(wait=False, cancel_futures=True)

    def run(self) -> None:
        total = len(self._paths)
        done = 0
        success = 0
        failures = 0
        skipped = 0
        self.log.emit(
            f"Démarrage de la conversion de {total} photo(s) "
            f"sur {self._max_workers} threads."
        )
        try:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
            futures = {
                self._executor.submit(
                    convert_heic_to_png,
                    path,
                    self._output_dir,
                    self._keep_exif,
                    self._overwrite,
                ): path
                for path in self._paths
            }
            for future in as_completed(futures):
                if self._cancelled:
                    break
                source = futures[future]
                try:
                    result: ConversionResult = future.result()
                except Exception as exc:  # noqa: BLE001
                    result = ConversionResult(source, None, False, str(exc))

                done += 1
                if result.skipped:
                    skipped += 1
                    self.log.emit(f"IGNORÉ  {os.path.basename(source)} (PNG déjà présent)")
                elif result.success:
                    success += 1
                    self.log.emit(
                        f"OK  {os.path.basename(source)} -> "
                        f"{os.path.basename(result.output or '')}"
                    )
                else:
                    failures += 1
                    self.log.emit(
                        f"ERREUR  {os.path.basename(source)} : {result.error}"
                    )
                self.item_done.emit(result)
                self.progress.emit(done, total)
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"Erreur du pool de conversion : {exc}")
        finally:
            if self._executor is not None:
                self._executor.shutdown(wait=False)
                self._executor = None
            self.log.emit(
                f"Terminé : {success} réussite(s), {failures} échec(s), {skipped} ignorée(s)."
            )
            self.finished.emit(success, failures, skipped)
