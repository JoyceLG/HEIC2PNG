"""Moteur de conversion HEIC -> PNG et extraction de métadonnées.

Les fonctions de ce module sont volontairement de niveau module (top-level)
afin de pouvoir être sérialisées (pickle) et exécutées dans un
``ProcessPoolExecutor``.
"""

from __future__ import annotations

import datetime as _dt
import os
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from PIL import Image, ExifTags
import pillow_heif

# Enregistre le décodeur HEIC/HEIF auprès de Pillow.
pillow_heif.register_heif_opener()

HEIC_EXTENSIONS = {".heic", ".heif", ".hif"}

# Index inverse pour traduire les tags EXIF numériques en noms lisibles.
_EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}
_GPS_TAGS = ExifTags.GPSTAGS


def is_heic(path: str) -> bool:
    """Retourne True si le chemin pointe vers un fichier HEIC/HEIF."""
    return os.path.splitext(path)[1].lower() in HEIC_EXTENSIONS


@dataclass
class PhotoMetadata:
    """Métadonnées extraites d'une photo HEIC."""

    width: int = 0
    height: int = 0
    file_size: int = 0
    created: str | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    orientation: int | None = None
    gps: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def dimensions(self) -> str:
        if self.width and self.height:
            return f"{self.width} x {self.height}"
        return "—"

    @property
    def file_size_human(self) -> str:
        return _human_size(self.file_size)


@dataclass
class ConversionResult:
    """Résultat d'une conversion individuelle."""

    source: str
    output: str | None
    success: bool
    error: str | None = None
    skipped: bool = False


def _human_size(num: float) -> str:
    """Convertit un nombre d'octets en chaîne lisible (Ko, Mo...)."""
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if abs(num) < 1024.0:
            return f"{num:.0f} {unit}" if unit == "o" else f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} Po"


def _decode_exif_value(value: Any) -> Any:
    """Rend une valeur EXIF sérialisable et lisible."""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", "replace").strip("\x00").strip()
        except Exception:
            return repr(value)
    if isinstance(value, _dt.datetime):
        return value.isoformat()
    return value


def _format_datetime(raw: str) -> str | None:
    """Normalise une date EXIF du type ``YYYY:MM:DD HH:MM:SS``."""
    if not raw:
        return None
    raw = str(raw).strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return _dt.datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return raw


def _convert_gps(coordinates: Any, ref: Any) -> float | None:
    """Convertit des coordonnées GPS EXIF en degrés décimaux."""
    try:
        degrees, minutes, seconds = (float(Fraction(str(c))) for c in coordinates)
        decimal = degrees + minutes / 60.0 + seconds / 3600.0
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except Exception:
        return None


def extract_metadata(path: str) -> PhotoMetadata:
    """Extrait largeur, hauteur, taille fichier et métadonnées EXIF d'un HEIC."""
    meta = PhotoMetadata()
    try:
        meta.file_size = os.path.getsize(path)
    except OSError:
        meta.file_size = 0

    try:
        with Image.open(path) as img:
            meta.width, meta.height = img.size
            exif = img.getexif()
            if exif:
                _populate_exif(meta, exif)
    except Exception as exc:  # noqa: BLE001 - métadonnées best effort
        meta.extra["erreur_lecture"] = str(exc)
    return meta


def _populate_exif(meta: PhotoMetadata, exif) -> None:
    """Remplit ``meta`` à partir d'un objet EXIF Pillow."""
    make = exif.get(_EXIF_TAGS.get("Make"))
    model = exif.get(_EXIF_TAGS.get("Model"))
    orientation = exif.get(_EXIF_TAGS.get("Orientation"))
    dt_original = exif.get(_EXIF_TAGS.get("DateTimeOriginal")) or exif.get(
        _EXIF_TAGS.get("DateTime")
    )

    meta.camera_make = _decode_exif_value(make) if make else None
    meta.camera_model = _decode_exif_value(model) if model else None
    meta.orientation = int(orientation) if orientation else None
    if dt_original:
        meta.created = _format_datetime(_decode_exif_value(dt_original))

    # Bloc GPS éventuel (IFD dédié).
    try:
        gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
    except Exception:
        gps_ifd = None
    if gps_ifd:
        gps = {_GPS_TAGS.get(k, k): v for k, v in gps_ifd.items()}
        lat = _convert_gps(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
        lon = _convert_gps(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
        if lat is not None and lon is not None:
            meta.gps = f"{lat}, {lon}"


def unique_destination(path: str) -> str:
    """Renvoie un chemin de sortie non utilisé en ajoutant un suffixe ``_N``."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 1
    candidate = f"{base}_{counter}{ext}"
    while os.path.exists(candidate):
        counter += 1
        candidate = f"{base}_{counter}{ext}"
    return candidate


def target_path(source: str, output_dir: str | None) -> str:
    """Calcule le chemin PNG de destination pour une source donnée.

    Si ``output_dir`` est ``None``, le PNG est écrit à côté de la source.
    """
    name = os.path.splitext(os.path.basename(source))[0] + ".png"
    folder = output_dir if output_dir else os.path.dirname(source)
    return os.path.join(folder, name)


def convert_heic_to_png(
    source: str,
    output_dir: str | None = None,
    keep_exif: bool = True,
    overwrite: bool = False,
) -> ConversionResult:
    """Convertit un fichier HEIC en PNG.

    Args:
        source: chemin du fichier HEIC.
        output_dir: dossier de destination, ou ``None`` pour écrire à côté.
        keep_exif: conserve les métadonnées EXIF dans le PNG si possible.
        overwrite: écrase la cible existante au lieu de renommer.

    Returns:
        Un ``ConversionResult`` décrivant l'issue de l'opération.
    """
    try:
        if not os.path.isfile(source):
            return ConversionResult(source, None, False, "Fichier introuvable")

        destination = target_path(source, output_dir)
        folder = os.path.dirname(destination)
        if folder:
            os.makedirs(folder, exist_ok=True)
        if not overwrite and os.path.exists(destination):
            return ConversionResult(source, destination, True, skipped=True)

        with Image.open(source) as img:
            save_kwargs: dict[str, Any] = {}
            if keep_exif:
                exif_bytes = img.info.get("exif")
                if exif_bytes:
                    save_kwargs["exif"] = exif_bytes
            img.save(destination, format="PNG", **save_kwargs)

        return ConversionResult(source, destination, True)
    except Exception as exc:  # noqa: BLE001 - on remonte l'erreur à l'UI
        return ConversionResult(source, None, False, str(exc))
