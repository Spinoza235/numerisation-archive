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
    # Page clairement française : une page arabe lue avec le modèle français donne
    # une confiance très basse (< 60). Au-dessus de 80, on gagne du temps.
    if conf_fr >= 80:
        return _nettoyer(texte_fr), "fr", round(conf_fr, 1)
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


# ---------- Sens de la page (document photographié couché ou à l'envers) ----------

ROTATIONS = {90: "ROTATE_90_CLOCKWISE", 180: "ROTATE_180", 270: "ROTATE_90_COUNTERCLOCKWISE"}


def _tourner_quart(image, angle):
    import cv2
    return image if angle == 0 else cv2.rotate(image, getattr(cv2, ROTATIONS[angle]))


def _mots_lisibles(image, langue):
    """Score de lisibilité : somme des confiances des vrais mots bien lus.
    Un texte couché ou à l'envers donne presque 0 ; un texte droit donne un score élevé."""
    data = pytesseract.image_to_data(image, lang=langue, config="--oem 1 --psm 6",
                                     output_type=pytesseract.Output.DICT)
    score, nb = 0.0, 0
    for mot, conf in zip(data["text"], data["conf"]):
        mot = mot.strip()
        if float(conf) > 60 and len(mot) >= 3 and sum(c.isalpha() for c in mot) >= 3:
            score += float(conf)
            nb += 1
    return score, nb


def orienter(image):
    """Remet la page dans le bon sens. Renvoie (image, angle appliqué : 0, 90, 180 ou 270).
    Cas courant (page déjà droite) : une seule lecture rapide, presque rien en plus.
    Sinon on essaie les 3 autres sens, en français et en arabe, et on garde le plus lisible."""
    import cv2
    echelle = min(1.0, 1300 / max(image.shape[:2]))
    petit = cv2.resize(image, None, fx=echelle, fy=echelle, interpolation=cv2.INTER_AREA)

    resultats = {}
    for langue in ("fra", "ara"):
        score, nb = _mots_lisibles(petit, langue)
        resultats[(0, langue)] = score
        if nb >= 12:  # assez de mots bien lus : la page est droite
            return image, 0
    for angle in (90, 270, 180):
        tourne = _tourner_quart(petit, angle)
        for langue in ("fra", "ara"):
            score, nb = _mots_lisibles(tourne, langue)
            resultats[(angle, langue)] = score
            if nb >= 12:  # sens trouvé sans hésitation : inutile d'essayer les autres
                return _tourner_quart(image, angle), angle
    angle = max(resultats, key=resultats.get)[0]
    # on ne tourne que si c'est nettement plus lisible qu'à l'origine
    if angle != 0 and resultats[max(resultats, key=resultats.get)] > 1.5 * max(resultats[(0, "fra")], resultats[(0, "ara")]) + 100:
        return _tourner_quart(image, angle), angle
    return image, 0


def lire_texte(image):
    """Renvoie (texte, langue 'fr'|'ar', confiance)."""
    if MOTEUR_OCR == "paddle":
        try:
            return lire_paddle(image)
        except ImportError:
            print("PaddleOCR non installé : utilisation de Tesseract.")
    return lire_tesseract(image)