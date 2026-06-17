# HEIC → PNG — Convertisseur

Application de bureau Python (PySide6) pour convertir en masse des photos
**HEIC/HEIF** en **PNG**, avec glisser-déposer, conversion parallèle
multi-cœurs, barre de progression, logs et affichage liste ou cartes triable.

## Fonctionnalités

- **Entrée** : glisser-déposer de photos ou de dossiers, ou sélection via
  les boutons « Ajouter des photos… » / « Ajouter un dossier… ».
- **Sortie** : dossier de destination unique, à côté de chaque photo, ou
  demande par lot. Conservation optionnelle des métadonnées EXIF et gestion
  des collisions (renommage automatique `_1`, `_2`… ou écrasement).
- **Conversion parallèle** via un `ProcessPoolExecutor` (tous les cœurs CPU).
- **Barre de progression** et **onglet Logs**.
- **Affichage liste** (tableau détaillé) ou **cartes** (vignettes), avec tri
  par nom, date, taille ou statut.
- **Panneau de détails** affichant les métadonnées de chaque photo
  (dimensions, taille, date de prise, appareil, orientation, GPS, statut).

## Installation

```bash
cd heic2png
python -m venv .venv
source .venv/bin/activate      # sous Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

```bash
python main.py
```

## Utilisation

1. Glissez vos photos HEIC (ou un dossier) dans la zone de dépôt, ou utilisez
   les boutons d'ajout.
2. Choisissez le mode de sortie et, le cas échéant, le dossier de destination.
3. Activez « Conserver les métadonnées EXIF » si souhaité.
4. Cliquez sur **Convertir** (toutes les photos en attente) ou
   **Convertir la sélection**.
5. Suivez l'avancement dans l'onglet *Progression* et les détails dans *Logs*.

## Structure

```
heic2png/
├── main.py                  # point d'entrée QApplication
├── requirements.txt
└── heic2png/
    ├── converter.py         # conversion + extraction métadonnées (multiprocessing)
    ├── worker.py            # workers Qt (métadonnées + conversion parallèle)
    └── ui/
        ├── main_window.py   # fenêtre principale
        ├── drop_zone.py     # zone de glisser-déposer
        ├── photo_model.py   # modèle de données des photos
        └── views.py         # vues liste / cartes + vignettes + tri
```

## Dépendances

- [PySide6](https://pypi.org/project/PySide6/) — interface graphique Qt.
- [Pillow](https://pypi.org/project/Pillow/) — encodage PNG et lecture EXIF.
- [pillow-heif](https://pypi.org/project/pillow-heif/) — décodage HEIC/HEIF.
