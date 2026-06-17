# HEIC → PNG

Application de bureau Python/PySide6 pour convertir des photos **HEIC/HEIF** en **PNG** sous Linux et Windows.

---

## Fonctionnalités

- **Glisser-déposer** de photos ou de dossiers entiers
- **Conversion parallèle** (multi-thread, CPU limité à 50 % pour rester réactif)
- **Détection automatique** : saute les photos déjà converties (optionnel : écrasement)
- **Préservation EXIF** optionnelle
- **Affichage liste ou cartes** avec tri par nom, date, taille ou statut
- **Panneau de détails** : dimensions, taille, date, appareil, GPS, orientation
- **Barre de progression modale** pendant le chargement des métadonnées
- **Journal de débogage** dans `~/.local/share/heic2png/debug.log`
- **Icônes natives** (thème système)

---

## Prérequis

### Linux

```bash
# Ubuntu / Debian
sudo apt install libheif1

# Fedora / RHEL
sudo dnf install libheif

# Arch
sudo pacman -S libheif
```

Python 3.11 ou supérieur.

### Windows

Python 3.11 ou supérieur. `pillow-heif` embarque ses propres binaires — aucune dépendance système supplémentaire.

---

## Installation depuis les sources

```bash
git clone <url-du-dépôt>
cd HEIC2PNG

python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate

pip install -r requirements.txt
```

## Lancement

```bash
# Linux / macOS
source .venv/bin/activate
python main.py

# Windows
.venv\Scripts\activate
python main.py
```

---

## Utilisation

1. Glissez vos photos HEIC (ou un dossier) dans la zone de dépôt, ou utilisez **Ajouter des photos…** / **Ajouter un dossier…**.
2. Choisissez le mode de sortie :
   - **Dossier destination unique** — tous les PNG dans un même dossier.
   - **À côté de chaque photo** — PNG créé dans le même dossier que la source.
   - **Demander par lot** — boîte de dialogue à chaque lancement.
3. Cochez **Conserver les métadonnées EXIF** si souhaité.
4. Cochez **Écraser les fichiers existants** pour reconvertir des photos déjà traitées.
5. Cliquez sur **Convertir** (toutes les photos en attente) ou **Convertir la sélection**.
6. Suivez l'avancement dans l'onglet *Progression* et les détails dans *Logs*.

**Statuts des photos :**

| Couleur  | Statut    | Signification                         |
|----------|-----------|---------------------------------------|
| Gris     | En attente | En file, pas encore traitée          |
| Bleu     | En cours  | Conversion en cours                   |
| Vert     | Convertie | Conversion réussie                    |
| Orange   | Ignorée   | PNG déjà présent (écrasement désactivé) |
| Rouge    | Erreur    | Échec de conversion                   |

---

## Créer un exécutable

### Linux

```bash
bash build_linux.sh
# Résultat : dist/heic2png/heic2png
```

Pour créer une archive distribuable :
```bash
tar -czf heic2png-linux.tar.gz -C dist heic2png
```

### Windows

Exécuter depuis une invite de commandes dans le dossier du projet :
```bat
build_windows.bat
:: Résultat : dist\heic2png\heic2png.exe
```

Pour créer une archive distribuable :
```powershell
Compress-Archive -Path dist\heic2png -DestinationPath heic2png-windows.zip
```

> **Note :** le build Linux doit être fait sur Linux, et le build Windows sur Windows. PyInstaller ne supporte pas la compilation croisée.

---

## Journal de débogage

Les logs sont écrits dans :
- **Linux / macOS** : `~/.local/share/heic2png/debug.log`
- **Windows** : `%USERPROFILE%\.local\share\heic2png\debug.log`

Niveaux enregistrés : actions utilisateur (INFO), détails de conversion (DEBUG), erreurs (WARNING).

---

## Structure du projet

```
HEIC2PNG/
├── main.py                  # Point d'entrée QApplication
├── requirements.txt         # Dépendances runtime
├── build_linux.sh           # Script de build Linux
├── build_windows.bat        # Script de build Windows
└── heic2png/
    ├── converter.py         # Conversion HEIC→PNG + extraction métadonnées
    ├── worker.py            # Workers Qt (scan, métadonnées, conversion)
    └── ui/
        ├── main_window.py   # Fenêtre principale
        ├── drop_zone.py     # Zone de glisser-déposer
        ├── photo_model.py   # Modèle de données (PhotoItem, PhotoStore, PhotoStatus)
        └── views.py         # Vues liste / cartes, vignettes, tri
```

---

## Dépendances

| Paquet | Rôle |
|--------|------|
| [PySide6](https://pypi.org/project/PySide6/) | Interface graphique Qt 6 |
| [Pillow](https://pypi.org/project/Pillow/) | Encodage PNG, lecture EXIF |
| [pillow-heif](https://pypi.org/project/pillow-heif/) | Décodage HEIC/HEIF via libheif |

---

## Licence

MIT
