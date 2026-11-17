"""
ocr.py — Lit le texte d'une image propre, en français ou en arabe.

Moteur par défaut : Tesseract (léger, gratuit, fonctionne hors ligne).
Moteur optionnel  : PaddleOCR (MOTEUR_OCR=paddle), plus lourd à installer.

Comment on choisit la langue : on lit l'image en français PUIS en arabe,
et on garde la lecture dont la "confiance" moyenne est la meilleure.
"""
import os
import re

import pytesseract

from config import MOTEUR_OCR, TESSDATA

if TESSDATA:
    os.environ["TESSDATA_PREFIX"] = TESSDATA

ARABE = re.compile(r"[؀-ۿ]")


def _tesseract(image, langue):
    """Renvoie (texte, confiance moyenne 0-100)."""
    config = "--oem 1 --psm 4"  # psm 4 : une colonne de texte, lignes de tailles variées
    data = pytesseract.image_to_data(image, lang=langue, config=config,
                                     output_type=pytesseract.Output.DICT)
    lignes, confs = {}, []
    for i, mot in enumerate(data["text"]):
        if not mot.strip():
            continue
        cle = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lignes.setdefault(cle, []).append(mot)
        if float(data["conf"][i]) >= 0:
            confs.append(float(data["conf"][i]))
    texte = "\n".join(" ".join(mots) for _, mots in sorted(lignes.items()))
    confiance = sum(confs) / len(confs) if confs else 0.0
    return texte, confiance


def _nettoyer(texte):
    lignes = [re.sub(r"[ \t]+", " ", l).strip() for l in texte.splitlines()]
    texte = "\n".join(l for l in lignes if l)
    return texte


def lire_tesseract(image):
    import cv2
    # Agrandir x1,5 améliore nettement la lecture (surtout l'arabe et les petits caractères)
    image = cv2.resize(image, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    texte_fr, conf_fr = _tesseract(image, "fra")
    texte_ar, conf_ar = _tesseract(image, "ara")
    # L'arabe lu avec le modèle français donne une confiance faible, et inversement.
    part_arabe = len(ARABE.findall(texte_ar)) / max(1, len(texte_ar.replace(" ", "")))
    if conf_ar > conf_fr and part_arabe > 0.4:
        return _nettoyer(texte_ar), "ar", round(conf_ar, 1)
    return _nettoyer(texte_fr), "fr", round(conf_fr, 1)


def lire_paddle(image):
    """Optionnel. pip install paddleocr paddlepaddle"""
    from paddleocr import PaddleOCR
    import numpy as np

    resultats = {}
    for langue, code in (("fr", "fr"), ("ar", "arabic")):
        moteur = PaddleOCR(lang=code, use_angle_cls=True, show_log=False)
        sortie = moteur.ocr(np.dstack([image] * 3) if image.ndim == 2 else image, cls=True)
        lignes = [l[1][0] for bloc in sortie or [] for l in (bloc or [])]
        confs = [l[1][1] for bloc in sortie or [] for l in (bloc or [])]
        resultats[langue] = ("\n".join(lignes), 100 * sum(confs) / len(confs) if confs else 0)
    langue = max(resultats, key=lambda k: resultats[k][1])
    texte, conf = resultats[langue]
    return _nettoyer(texte), langue, round(conf, 1)


def lire_titre(image, langue):
    """Deuxième lecture, seulement du HAUT de la page (30 %), à deux échelles.
    Les gros titres ("FACTURE", "محضر اجتماع") sont parfois sautés par la lecture
    principale : cette passe les rattrape. Elle sert à reconnaître le type de document."""
    import cv2
    code = "ara" if langue == "ar" else "fra"
    haut = image[: int(image.shape[0] * 0.3)]
    morceaux = []
    for echelle, psm in ((1.0, "6"), (0.7, "11")):
        img = cv2.resize(haut, None, fx=echelle, fy=echelle, interpolation=cv2.INTER_AREA)
        morceaux.append(pytesseract.image_to_string(img, lang=code, config=f"--oem 1 --psm {psm}"))
    return _nettoyer("\n".join(morceaux))


def lire_texte(image):
    """Renvoie (texte, langue 'fr'|'ar', confiance)."""
    if MOTEUR_OCR == "paddle":
        try:
            return lire_paddle(image)
        except ImportError:
            print("PaddleOCR non installé : utilisation de Tesseract.")
    return lire_tesseract(image)
