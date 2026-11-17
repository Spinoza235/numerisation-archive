"""
pretraitement.py — Nettoie une photo ou un scan avant la lecture (OCR).

Étapes :
  1. trouver la feuille dans la photo et la remettre à plat (perspective) ;
  2. redresser le texte s'il est penché (inclinaison) ;
  3. effacer les ombres et l'éclairage inégal ;
  4. produire une image en niveaux de gris propre, prête pour l'OCR.
"""
from pathlib import Path

import cv2
import numpy as np


def lire_image(chemin: Path):
    """cv2.imread ne gère pas toujours les accents dans les chemins : on passe par imdecode."""
    data = np.fromfile(str(chemin), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def ecrire_image(chemin: Path, image):
    ok, buf = cv2.imencode(chemin.suffix or ".png", image)
    if ok:
        buf.tofile(str(chemin))


# ---------- 1. Trouver la feuille et la remettre à plat ----------

def _ordonner_coins(pts):
    pts = pts.reshape(4, 2).astype(np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], np.float32)


def redresser_perspective(image):
    """Cherche le plus grand quadrilatère clair (la feuille). Si on le trouve, on le
    'découpe' et on le remet à plat. Sinon, on garde l'image telle quelle (cas d'un scan)."""
    h, w = image.shape[:2]
    echelle = 800 / max(h, w)
    petit = cv2.resize(image, None, fx=echelle, fy=echelle)
    gris = cv2.cvtColor(petit, cv2.COLOR_BGR2GRAY)
    gris = cv2.GaussianBlur(gris, (5, 5), 0)
    _, masque = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    masque = cv2.morphologyEx(masque, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(masque, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image, False

    plus_grand = max(contours, key=cv2.contourArea)
    aire = cv2.contourArea(plus_grand)
    # La feuille doit occuper une bonne partie de la photo, sans être la photo entière
    if not (0.25 * petit.shape[0] * petit.shape[1] < aire < 0.97 * petit.shape[0] * petit.shape[1]):
        return image, False

    approx = cv2.approxPolyDP(plus_grand, 0.02 * cv2.arcLength(plus_grand, True), True)
    if len(approx) != 4:
        return image, False

    coins = _ordonner_coins(approx) / echelle
    (tl, tr, br, bl) = coins
    largeur = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    hauteur = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    cible = np.array([[0, 0], [largeur - 1, 0], [largeur - 1, hauteur - 1], [0, hauteur - 1]], np.float32)
    M = cv2.getPerspectiveTransform(coins, cible)
    return cv2.warpPerspective(image, M, (largeur, hauteur)), True


# ---------- 2. Redresser l'inclinaison ----------

def angle_inclinaison(gris):
    """Méthode des profils : on fait tourner l'image de -10° à +10° et on garde l'angle
    où les lignes de texte sont les plus nettes (forte variation ligne / interligne)."""
    petit = cv2.resize(gris, None, fx=0.5, fy=0.5)
    _, binaire = cv2.threshold(petit, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    h, w = binaire.shape
    centre = (w / 2, h / 2)

    def score(angle):
        M = cv2.getRotationMatrix2D(centre, angle, 1.0)
        rot = cv2.warpAffine(binaire, M, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
        profil = rot.sum(axis=1, dtype=np.float64)
        return np.var(profil)

    meilleur = max(np.arange(-10, 10.01, 0.5), key=score)
    fin = max(np.arange(meilleur - 0.5, meilleur + 0.51, 0.1), key=score)
    return float(fin)


def tourner(image, angle):
    h, w = image.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    M[0, 2] += nw / 2 - w / 2
    M[1, 2] += nh / 2 - h / 2
    fond = 255 if image.ndim == 2 else (255, 255, 255)
    return cv2.warpAffine(image, M, (nw, nh), flags=cv2.INTER_CUBIC, borderValue=fond)


# ---------- 3. Effacer les ombres ----------

def normaliser_eclairage(gris):
    """On estime le 'fond' de la feuille (une version très floue de l'image) et on divise
    l'image par ce fond : les ombres et zones sombres deviennent blanches, le texte reste noir."""
    fond = cv2.medianBlur(cv2.dilate(gris, np.ones((7, 7), np.uint8)), 31)
    norm = cv2.divide(gris, fond, scale=255)
    return cv2.normalize(norm, None, 0, 255, cv2.NORM_MINMAX)


# ---------- Pipeline complet ----------

def pretraiter(image):
    """Renvoie (image_propre_en_gris, infos)."""
    infos = {}
    image, a_plat = redresser_perspective(image)
    infos["perspective_corrigee"] = a_plat

    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gris = normaliser_eclairage(gris)

    angle = angle_inclinaison(gris)
    infos["angle_corrige"] = round(angle, 1)
    if abs(angle) >= 0.2:
        gris = tourner(gris, angle)

    # léger débruitage + contraste
    gris = cv2.fastNlMeansDenoising(gris, None, h=8, templateWindowSize=7, searchWindowSize=21)
    return gris, infos
