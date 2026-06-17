"""Fenêtre principale de l'application HEIC -> PNG."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..converter import ConversionResult, is_heic
from ..worker import ConversionWorker, MetadataWorker
from .drop_zone import DropZone, _scan_dir
from .photo_model import PhotoItem, PhotoStore, PhotoStatus
from .views import PhotoGallery, ThumbnailLoader


class MainWindow(QMainWindow):
    """Fenêtre principale orchestrant l'ajout, l'affichage et la conversion."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HEIC → PNG — Convertisseur")
        self.resize(1100, 720)

        self.store = PhotoStore()
        self._threads: list[tuple] = []
        self._conversion_thread: QThread | None = None
        self._conversion_worker: ConversionWorker | None = None

        self._build_ui()

    # ----- Construction de l'interface ---------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        root.addWidget(self._build_top_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.gallery = PhotoGallery(self.store)
        self.gallery.selection_changed.connect(self._on_selection_changed)
        splitter.addWidget(self.gallery)
        splitter.addWidget(self._build_detail_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        root.addWidget(self._build_output_controls())
        root.addWidget(self._build_progress_and_logs())

    def _build_top_bar(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)

        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self.add_paths)
        layout.addWidget(self.drop_zone)

        buttons = QHBoxLayout()
        add_files_btn = QPushButton("Ajouter des photos…")
        add_files_btn.clicked.connect(self._choose_files)
        add_folder_btn = QPushButton("Ajouter un dossier…")
        add_folder_btn.clicked.connect(self._choose_folder)
        self.remove_btn = QPushButton("Retirer la sélection")
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn = QPushButton("Tout vider")
        self.clear_btn.clicked.connect(self._clear_all)
        self.count_label = QLabel("0 photo")
        buttons.addWidget(add_files_btn)
        buttons.addWidget(add_folder_btn)
        buttons.addWidget(self.remove_btn)
        buttons.addWidget(self.clear_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.count_label)
        layout.addLayout(buttons)
        return box

    def _build_detail_panel(self) -> QWidget:
        group = QGroupBox("Détails de la photo")
        layout = QVBoxLayout(group)
        self.detail_thumb = QLabel("Aucune sélection")
        self.detail_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_thumb.setMinimumHeight(180)
        self.detail_thumb.setStyleSheet("background:#f1f3f4; border-radius:6px;")
        layout.addWidget(self.detail_thumb)

        self.detail_form = QFormLayout()
        self.detail_fields = {
            "name": QLabel("—"),
            "path": QLabel("—"),
            "dimensions": QLabel("—"),
            "size": QLabel("—"),
            "created": QLabel("—"),
            "camera": QLabel("—"),
            "orientation": QLabel("—"),
            "gps": QLabel("—"),
            "status": QLabel("—"),
            "output": QLabel("—"),
        }
        labels = {
            "name": "Nom",
            "path": "Chemin",
            "dimensions": "Dimensions",
            "size": "Taille",
            "created": "Date de prise",
            "camera": "Appareil",
            "orientation": "Orientation",
            "gps": "GPS",
            "status": "Statut",
            "output": "Sortie",
        }
        for key, field in self.detail_fields.items():
            field.setWordWrap(True)
            field.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.detail_form.addRow(labels[key] + " :", field)
        layout.addLayout(self.detail_form)
        layout.addStretch(1)
        return group

    def _build_output_controls(self) -> QWidget:
        group = QGroupBox("Sortie")
        layout = QVBoxLayout(group)

        mode_row = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.mode_dest = QRadioButton("Dossier destination unique")
        self.mode_same = QRadioButton("À côté de chaque photo")
        self.mode_ask = QRadioButton("Demander par lot")
        self.mode_dest.setChecked(True)
        for btn in (self.mode_dest, self.mode_same, self.mode_ask):
            self.mode_group.addButton(btn)
            mode_row.addWidget(btn)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        dest_row = QHBoxLayout()
        self.dest_edit = QLineEdit()
        self.dest_edit.setPlaceholderText("Dossier de destination…")
        browse_btn = QPushButton("Parcourir…")
        browse_btn.clicked.connect(self._choose_destination)
        dest_row.addWidget(QLabel("Destination :"))
        dest_row.addWidget(self.dest_edit, 1)
        dest_row.addWidget(browse_btn)
        layout.addLayout(dest_row)

        options_row = QHBoxLayout()
        self.keep_exif_chk = QCheckBox("Conserver les métadonnées EXIF")
        self.keep_exif_chk.setChecked(True)
        self.overwrite_chk = QCheckBox("Écraser les fichiers existants")
        options_row.addWidget(self.keep_exif_chk)
        options_row.addWidget(self.overwrite_chk)
        options_row.addStretch(1)
        layout.addLayout(options_row)

        action_row = QHBoxLayout()
        self.convert_btn = QPushButton("Convertir")
        self.convert_btn.clicked.connect(self._start_conversion)
        self.convert_selected_btn = QPushButton("Convertir la sélection")
        self.convert_selected_btn.clicked.connect(self._start_conversion_selected)
        self.cancel_btn = QPushButton("Annuler")
        self.cancel_btn.clicked.connect(self._cancel_conversion)
        self.cancel_btn.setEnabled(False)
        action_row.addStretch(1)
        action_row.addWidget(self.convert_selected_btn)
        action_row.addWidget(self.convert_btn)
        action_row.addWidget(self.cancel_btn)
        layout.addLayout(action_row)
        return group

    def _build_progress_and_logs(self) -> QWidget:
        tabs = QTabWidget()
        tabs.setMaximumHeight(200)

        progress_page = QWidget()
        p_layout = QVBoxLayout(progress_page)
        self.progress = QProgressBar()
        self.progress.setFormat("%v / %m (%p%)")
        self.progress_label = QLabel("Prêt.")
        p_layout.addWidget(self.progress_label)
        p_layout.addWidget(self.progress)
        p_layout.addStretch(1)
        tabs.addTab(progress_page, "Progression")

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        tabs.addTab(self.log_view, "Logs")
        return tabs

    # ----- Ajout de photos ---------------------------------------------
    def _choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Choisir des photos HEIC", "", "Images HEIC (*.heic *.heif *.hif)"
        )
        if files:
            self.add_paths(files)

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choisir un dossier")
        if folder:
            self.add_paths(_scan_dir(folder))

    def _choose_destination(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Dossier de destination")
        if folder:
            self.dest_edit.setText(folder)
            self.mode_dest.setChecked(True)

    def add_paths(self, paths: list[str]) -> None:
        """Ajoute des chemins HEIC au store et lance le chargement asynchrone."""
        new_items: list[PhotoItem] = []
        for path in paths:
            if not is_heic(path):
                continue
            item = self.store.add(path)
            if item is not None:
                new_items.append(item)
        if not new_items:
            return
        self.gallery.refresh()
        self._update_count()
        self._log(f"{len(new_items)} photo(s) ajoutée(s).")
        self._load_metadata([i.path for i in new_items])
        self._load_thumbnails([i.path for i in new_items])

    def _remove_selected(self) -> None:
        paths = self.gallery.selected_paths()
        if not paths:
            return
        self.store.remove(paths)
        self.gallery.refresh()
        self._update_count()

    def _clear_all(self) -> None:
        self.store.clear()
        self.gallery.refresh()
        self._update_count()
        self._on_selection_changed(None)

    def _update_count(self) -> None:
        self.count_label.setText(f"{len(self.store)} photo(s)")

    # ----- Workers asynchrones -----------------------------------------
    def _run_worker(self, worker, on_finished=None) -> None:
        """Démarre un worker QObject dans un QThread géré."""
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        thread.finished.connect(lambda: self._cleanup_thread(thread, worker))
        if on_finished is not None:
            worker.finished.connect(on_finished)
        self._threads.append((thread, worker))
        thread.start()

    def _cleanup_thread(self, thread, worker) -> None:
        entry = (thread, worker)
        if entry in self._threads:
            self._threads.remove(entry)
        worker.deleteLater()
        thread.deleteLater()

    def _load_metadata(self, paths: list[str]) -> None:
        worker = MetadataWorker(paths)
        worker.loaded.connect(self._on_metadata_loaded)
        self._run_worker(worker)

    def _on_metadata_loaded(self, path: str, meta) -> None:
        item = self.store.get(path)
        if item is None:
            return
        item.metadata = meta
        self.gallery.refresh()
        if self._current_path == path:
            self._on_selection_changed(item)

    def _load_thumbnails(self, paths: list[str]) -> None:
        worker = ThumbnailLoader(paths)
        worker.ready.connect(self.gallery.set_thumbnail)
        self._run_worker(worker)

    # ----- Conversion ---------------------------------------------------
    def _resolve_output_dir(self) -> str | None | bool:
        """Détermine le dossier de sortie selon le mode choisi.

        Renvoie un chemin, ``None`` (à côté de la source) ou ``False`` si
        l'utilisateur a annulé la sélection.
        """
        if self.mode_same.isChecked():
            return None
        if self.mode_ask.isChecked():
            folder = QFileDialog.getExistingDirectory(self, "Dossier pour ce lot")
            return folder or False
        folder = self.dest_edit.text().strip()
        if not folder:
            QMessageBox.warning(
                self, "Destination manquante", "Choisissez un dossier de destination."
            )
            return False
        return folder

    def _start_conversion(self) -> None:
        paths = [i.path for i in self.store if i.status != PhotoStatus.DONE]
        self._launch_conversion(paths)

    def _start_conversion_selected(self) -> None:
        selected = self.gallery.selected_paths()
        paths = [p for p in selected if p]
        if not paths:
            QMessageBox.information(self, "Sélection vide", "Aucune photo sélectionnée.")
            return
        self._launch_conversion(paths)

    def _launch_conversion(self, paths: list[str]) -> None:
        if self._conversion_thread is not None:
            QMessageBox.information(
                self, "Conversion en cours", "Une conversion est déjà en cours."
            )
            return
        if not paths:
            QMessageBox.information(self, "Rien à convertir", "Aucune photo à convertir.")
            return
        output_dir = self._resolve_output_dir()
        if output_dir is False:
            return

        for path in paths:
            item = self.store.get(path)
            if item is not None:
                item.status = PhotoStatus.PENDING
                item.error = None
        self.gallery.refresh()

        self.progress.setRange(0, len(paths))
        self.progress.setValue(0)
        self.progress_label.setText(f"Conversion de {len(paths)} photo(s)…")
        self._set_converting(True)

        worker = ConversionWorker(
            paths,
            output_dir,
            keep_exif=self.keep_exif_chk.isChecked(),
            overwrite=self.overwrite_chk.isChecked(),
        )
        worker.progress.connect(self._on_progress)
        worker.item_done.connect(self._on_item_done)
        worker.log.connect(self._log)
        worker.finished.connect(self._on_conversion_finished)

        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        # Les références ne sont libérées qu'une fois le thread réellement arrêté,
        # pour éviter de détruire un QThread encore en cours d'exécution.
        thread.finished.connect(self._on_conversion_thread_finished)
        self._conversion_thread = thread
        self._conversion_worker = worker
        thread.start()

    def _cancel_conversion(self) -> None:
        if self._conversion_worker is not None:
            self._conversion_worker.cancel()
            self.cancel_btn.setEnabled(False)

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setValue(done)
        self.progress_label.setText(f"Conversion : {done}/{total}")

    def _on_item_done(self, result: ConversionResult) -> None:
        item = self.store.get(result.source)
        if item is None:
            return
        if result.success:
            item.status = PhotoStatus.DONE
            item.output_path = result.output
        else:
            item.status = PhotoStatus.ERROR
            item.error = result.error
        self.gallery.refresh()
        if self._current_path == result.source:
            self._on_selection_changed(item)

    def _on_conversion_finished(self, success: int, failures: int) -> None:
        self._set_converting(False)
        self.progress_label.setText(
            f"Terminé : {success} réussite(s), {failures} échec(s)."
        )

    def _on_conversion_thread_finished(self) -> None:
        thread = self._conversion_thread
        worker = self._conversion_worker
        self._conversion_thread = None
        self._conversion_worker = None
        if worker is not None:
            worker.deleteLater()
        if thread is not None:
            thread.deleteLater()

    def _set_converting(self, converting: bool) -> None:
        self.convert_btn.setEnabled(not converting)
        self.convert_selected_btn.setEnabled(not converting)
        self.cancel_btn.setEnabled(converting)

    # ----- Sélection / détails -----------------------------------------
    _current_path: str | None = None

    def _on_selection_changed(self, item: PhotoItem | None) -> None:
        self._current_path = item.path if item else None
        if item is None:
            self.detail_thumb.clear()
            self.detail_thumb.setText("Aucune sélection")
            for field in self.detail_fields.values():
                field.setText("—")
            return

        pixmap = self.gallery._thumbnails.get(item.path)
        if pixmap is not None:
            self.detail_thumb.setPixmap(
                pixmap.scaled(
                    self.detail_thumb.width(),
                    180,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.detail_thumb.setText("(vignette en cours…)")

        meta = item.metadata
        self.detail_fields["name"].setText(item.name)
        self.detail_fields["path"].setText(item.path)
        self.detail_fields["dimensions"].setText(item.dimensions)
        self.detail_fields["size"].setText(meta.file_size_human if meta else "—")
        self.detail_fields["created"].setText((meta.created if meta else None) or "—")
        camera = "—"
        if meta:
            parts = [p for p in (meta.camera_make, meta.camera_model) if p]
            camera = " ".join(parts) if parts else "—"
        self.detail_fields["camera"].setText(camera)
        self.detail_fields["orientation"].setText(
            str(meta.orientation) if meta and meta.orientation else "—"
        )
        self.detail_fields["gps"].setText((meta.gps if meta else None) or "—")
        self.detail_fields["status"].setText(item.status.value)
        self.detail_fields["output"].setText(item.output_path or item.error or "—")

    # ----- Utilitaires --------------------------------------------------
    def _log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._conversion_worker is not None:
            self._conversion_worker.cancel()
        # Arrête et attend tous les workers d'arrière-plan.
        for thread, worker in list(self._threads):
            if hasattr(worker, "cancel"):
                worker.cancel()
            thread.quit()
            thread.wait(2000)
        if self._conversion_thread is not None:
            self._conversion_thread.quit()
            self._conversion_thread.wait(2000)
        super().closeEvent(event)
