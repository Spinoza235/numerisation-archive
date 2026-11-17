"""
indexation.py — Le pipeline complet, document par document :

  image  ->  nettoyage (OpenCV)  ->  lecture (OCR)  ->  extraction (date, type)
         ->  fiche JSON  ->  index de recherche (Meilisearch)

Lancement :  python indexation.py            (traite tout le dossier documents/)
             python indexation.py ma_photo.jpg  (un seul fichier)
"""
import json
import re
import sys
import time
from pathlib import Path

from config import DOSSIER_DOCUMENTS, DOSSIER_FICHES, DOSSIER_PROPRES, EXTENSIONS_IMAGES
from extraction import extraire, normaliser
from ocr import lire_texte, lire_titre
from pretraitement import ecrire_image, lire_image, pretraiter
from recherche import Moteur


def traiter_document(chemin: Path):
    """Traite UNE image et renvoie sa fiche (dictionnaire)."""
    debut = time.perf_counter()
    image = lire_image(chemin)
    if image is None:
        raise ValueError(f"Image illisible : {chemin.name}")

    propre, infos = pretraiter(image)
    # Meilisearch n'accepte que lettres, chiffres, - et _ dans un identifiant
    # ("WhatsApp Image 2026-09-27 at 2.25.19 PM" -> "WhatsApp_Image_2026-09-27_at_2_25_19_PM")
    identifiant = re.sub(r"[^A-Za-z0-9_-]+", "_", chemin.stem).strip("_")[:100] or "document"
    chemin_propre = DOSSIER_PROPRES / f"{identifiant}.png"
    ecrire_image(chemin_propre, propre)

    texte, langue, confiance = lire_texte(propre)
    texte_titre = lire_titre(propre, langue)
    infos_extraites = extraire(texte, texte_titre)

    fiche = {
        "id": identifiant,
        "fichier": chemin.name,
        "image_origine": str(chemin.relative_to(chemin.parents[1])),
        "image_propre": str(chemin_propre.relative_to(chemin_propre.parents[2])),
        "langue": langue,
        "confiance_ocr": confiance,
        "texte": texte,
        "texte_haut": texte_titre,  # 2e lecture du haut de la page (rattrape des lignes sautées)
        "texte_normalise": normaliser(texte),  # aide la recherche sans accents
        **infos_extraites,
        **infos,
        "duree_traitement_s": round(time.perf_counter() - debut, 1),
    }
    (DOSSIER_FICHES / f"{identifiant}.json").write_text(
        json.dumps(fiche, ensure_ascii=False, indent=2), encoding="utf-8")
    return fiche


def main():
    if len(sys.argv) > 1:
        fichiers = [Path(a).resolve() for a in sys.argv[1:]]
    else:
        fichiers = sorted(p for p in DOSSIER_DOCUMENTS.iterdir() if p.suffix.lower() in EXTENSIONS_IMAGES)

    moteur = Moteur()
    print(f"Moteur de recherche : {moteur.nom}")
    moteur.preparer_index()

    fiches = []
    for chemin in fichiers:
        try:
            fiche = traiter_document(chemin)
        except Exception as e:  # un document raté ne bloque pas les autres
            print(f"  ERREUR {chemin.name} : {e}")
            continue
        fiches.append(fiche)
        print(f"  {fiche['fichier']:<12} {fiche['langue']}  {fiche['type']:<24} "
              f"{fiche['date'] or '—':<11} confiance {fiche['confiance_ocr']:>5}  "
              f"({fiche['duree_traitement_s']} s)")

    # Meilisearch : on n'envoie pas le texte normalisé (il gère lui-même les accents)
    moteur.ajouter([{k: v for k, v in f.items() if k != "texte_normalise"} for f in fiches])
    print(f"\n{len(fiches)} documents traités et indexés.")


if __name__ == "__main__":
    main()