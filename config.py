"""
config.py — Réglages du projet (chemins, OCR, moteur de recherche).
Modifiez ici, pas dans le reste du code.
"""
import os
from pathlib import Path

RACINE = Path(__file__).resolve().parent

# Dossiers
DOSSIER_DOCUMENTS = RACINE / "documents"          # images d'origine (scans, photos)
DOSSIER_DONNEES = RACINE / "donnees"              # résultats : images nettoyées + fiches JSON
DOSSIER_PROPRES = DOSSIER_DONNEES / "images_propres"
DOSSIER_FICHES = DOSSIER_DONNEES / "fiches"
DOSSIER_POLICES = RACINE / "polices"

for d in (DOSSIER_DOCUMENTS, DOSSIER_PROPRES, DOSSIER_FICHES):
    d.mkdir(parents=True, exist_ok=True)

EXTENSIONS_IMAGES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

# OCR
# "tesseract" (par défaut, léger) ou "paddle" (PaddleOCR, à installer en plus)
MOTEUR_OCR = os.getenv("MOTEUR_OCR", "tesseract")
# Dossier des modèles Tesseract (fra.traineddata, ara.traineddata).
# Laissez vide pour utiliser celui de votre installation.
TESSDATA = os.getenv("TESSDATA_PREFIX", "")

# Recherche : Meilisearch si disponible, sinon recherche locale intégrée
MEILI_URL = os.getenv("MEILI_URL", "http://127.0.0.1:7700")
MEILI_CLE = os.getenv("MEILI_MASTER_KEY", "")
MEILI_INDEX = "documents"

# Mode public (démo en ligne) : les documents déposés par les visiteurs sont analysés
# et affichés à CE visiteur seulement, puis effacés. Ils ne rejoignent jamais l'index commun.
# Activer avec la variable d'environnement MODE_PUBLIC=1 (ou dans les "Secrets" de Streamlit Cloud).
MODE_PUBLIC = os.getenv("MODE_PUBLIC", "0") == "1"

# Nom affiché dans l'interface
NOM_APPLICATION = os.getenv("NOM_APPLICATION", "Archives intelligentes")