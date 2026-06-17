"""Workers Qt pour l'extraction de métadonnées et la conversion parallèle."""

from __future__ import annotations

import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

from PySide6.QtCore import QObject, Signal

from .converter import (
    ConversionResult,
    PhotoMetadata,
    convert_heic_to_png,
    extract_metadata,
)


def _metadata_job(path: str) -> tuple[str, PhotoMetadata]:
    """Tâche exécutée en thread pour lire les métadonnées d'un fichier."""
    return path, extract_metadata(path)


class MetadataWorker(QObject):
    """Charge les métadonnées des photos en arrière-plan (threads d'E/S)."""

    loaded = Signal(str, object)  # chemin, PhotoMetadata
    finished = Signal()

    def __init__(self, paths: list[str], max_workers: int | None = None) -> None:
        super().__init__()
        self._paths = paths
        self._max_workers = max_workers or min(8, (os.cpu_count() or 4))
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
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
                        continue
        finally:
            self.finished.emit()


class ConversionWorker(QObject):
    """Convertit les photos HEIC en PNG via un pool de processus."""

    progress = Signal(int, int)  # terminés, total
    item_done = Signal(object)  # ConversionResult
    log = Signal(str)
    finished = Signal(int, int)  # succès, échecs

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
        self._max_workers = max_workers or (os.cpu_count() or 4)
        self._cancelled = False
        self._executor: ProcessPoolExecutor | None = None

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
        self.log.emit(
            f"Démarrage de la conversion de {total} photo(s) "
            f"sur {self._max_workers} processus."
        )
        try:
            # Contexte « spawn » : indispensable car le processus hôte contient
            # déjà des threads Qt ; un fork provoquerait des plantages.
            ctx = multiprocessing.get_context("spawn")
            self._executor = ProcessPoolExecutor(
                max_workers=self._max_workers, mp_context=ctx
            )
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
                if result.success:
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
                f"Terminé : {success} réussite(s), {failures} échec(s)."
            )
            self.finished.emit(success, failures)
