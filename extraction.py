"""
extraction.py — Tire les informations utiles du texte lu : date, type de document, titre, montant.

Tout est fait avec des règles simples (expressions régulières + listes de mots-clés),
ce qui est rapide, gratuit et facile à expliquer à un client.
Pour l'arabe, l'OCR fait parfois de petites erreurs (ex. "شبادة" au lieu de "شهادة") :
on compare donc les mots-clés avec une tolérance (rapidfuzz).
"""
import re
import unicodedata
from datetime import date

from rapidfuzz import fuzz

# ---------- Normalisation ----------

CHIFFRES_ARABES = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, chiffres arabes -> 0-9, formes de l'alif unifiées.
    Sert à comparer et à chercher sans se soucier de l'écriture exacte."""
    texte = texte.translate(CHIFFRES_ARABES).lower()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")  # accents + voyelles arabes
    texte = re.sub("[إأآا]", "ا", texte).replace("ة", "ه").replace("ى", "ي").replace("ـ", "")
    return texte


# ---------- Dates ----------

MOIS_FR = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
           "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
           # abréviations courantes
           "janv": 1, "fev": 2, "fevr": 2, "avr": 4, "juil": 7, "sept": 9, "oct": 10, "nov": 11, "dec": 12}
MOIS_AR = {"يناير": 1, "جانفي": 1, "فبراير": 2, "فيفري": 2, "مارس": 3, "ابريل": 4, "افريل": 4,
           "مايو": 5, "ماي": 5, "يونيو": 6, "جوان": 6, "يوليو": 7, "جويليه": 7, "اغسطس": 8,
           "اوت": 8, "سبتمبر": 9, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12}
TOUS_MOIS = {**MOIS_FR, **{normaliser(k): v for k, v in MOIS_AR.items()}}

RE_NUMERIQUE = re.compile(r"\b(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4})\b")
RE_ISO = re.compile(r"\b(\d{4})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{1,2})\b")
RE_LETTRES = re.compile(r"\b(\d{1,2})(?:er)?\s+([^\W\d_]+)\.?\s+(\d{4})\b")


def _valide(a, m, j):
    try:
        d = date(int(a), int(m), int(j))
        return d if 1950 <= d.year <= 2100 else None
    except ValueError:
        return None


def trouver_dates(texte: str):
    """Toutes les dates du texte, dans l'ordre où elles apparaissent."""
    t = normaliser(texte)
    trouvees = []
    for m in RE_NUMERIQUE.finditer(t):
        d = _valide(m.group(3), m.group(2), m.group(1))
        if d:
            trouvees.append((m.start(), d))
    for m in RE_ISO.finditer(t):
        d = _valide(m.group(1), m.group(2), m.group(3))
        if d:
            trouvees.append((m.start(), d))
    for m in RE_LETTRES.finditer(t):
        mois = TOUS_MOIS.get(m.group(2))
        if mois is None:  # tolérance aux erreurs d'OCR sur le nom du mois
            meilleur = max(TOUS_MOIS, key=lambda k: fuzz.ratio(k, m.group(2)))
            if fuzz.ratio(meilleur, m.group(2)) >= 80:
                mois = TOUS_MOIS[meilleur]
        if mois:
            d = _valide(m.group(3), mois, m.group(1))
            if d:
                trouvees.append((m.start(), d))
    return [d for _, d in sorted(trouvees)]


# « N'Djamena, le … », « Fait à …, le … », « انجمينا في … », « بتاريخ … »
RE_LIEU_DATE = re.compile(r"(,\s*le\b|\bfait a\b.*\ble\b|في|بتاريخ)")


def date_du_document(texte: str):
    """1) Une date écrite après « Ville, le … » (ou « في … » en arabe) est la date du document.
    2) Sinon, on prend la DERNIÈRE date écrite : les dates plus haut sont souvent des dates
       citées dans le texte (naissance, embauche, textes de loi…)."""
    for ligne in normaliser(texte).splitlines():
        for d in trouver_dates(ligne):
            debut_date = ligne.find(str(d.year))
            if RE_LIEU_DATE.search(ligne[:debut_date]):
                return d
    dates = trouver_dates(texte)
    return dates[-1] if dates else None


# ---------- Type de document ----------

# (type affiché, type en arabe, mots-clés français, mots-clés arabes)
TYPES = [
    ("Facture", "فاتورة", ["facture"], ["فاتوره"]),
    ("Bon de commande", "طلب شراء", ["bon de commande"], ["طلب شراء"]),
    ("Reçu", "إيصال", ["recu de paiement", "recu"], ["ايصال"]),
    ("Attestation de travail", "شهادة عمل", ["attestation de travail"], ["شهاده عمل"]),
    ("Attestation de stage", "شهادة تدريب", ["attestation de stage"], ["شهاده تدريب"]),
    ("Certificat de scolarité", "شهادة مدرسية", ["certificat de scolarite"], ["شهاده مدرسيه"]),
    ("Contrat", "عقد", ["contrat", "bail"], ["عقد"]),
    ("Procès-verbal", "محضر", ["proces-verbal", "proces verbal"], ["محضر"]),
    ("Convocation", "استدعاء", ["convocation"], ["استدعاء"]),
    ("Note de service", "مذكرة", ["note de service"], ["مذكره"]),
    ("Communiqué", "بلاغ", ["communique"], ["بلاغ", "بيان"]),
    ("Avis", "إعلان", ["avis"], ["اعلان"]),
    ("Décision", "قرار", ["decision", "arrete"], ["قرار"]),
    ("Circulaire", "تعميم", ["circulaire"], ["تعميم"]),
    ("Demande", "طلب", ["demande d'emploi", "demande"], ["طلب"]),
    ("Attestation", "شهادة", ["attestation", "certificat"], ["شهاده"]),
]


ARABE = re.compile(r"[\u0600-\u06FF]")


def _exact(texte_norm, mot):
    """Position du mot-clé écrit en entier (pas à l'intérieur d'un autre mot), ou None."""
    m = re.search(r"(?<!\w)" + re.escape(mot) + r"(?!\w)", texte_norm)
    return m.start() if m else None


def _approche(texte_norm, mot):
    """Position d'un mot-clé lu avec une petite erreur d'OCR (ex. "شبادة" pour "شهادة",
    "PROCÈÉS-VERBAL"), ou None. On compare sans les espaces, que l'OCR ajoute parfois au milieu des mots."""
    if len(mot.replace(" ", "")) < 5:
        return None
    compact_mot = mot.replace(" ", "")
    compact = texte_norm.replace(" ", "")
    a = fuzz.partial_ratio_alignment(compact_mot, compact)
    if a and a.score >= 85:
        return a.dest_start
    return None


def _meilleur_type(zone, chercher):
    candidats = []
    z = normaliser(zone)
    for nom, nom_ar, mots_fr, mots_ar in TYPES:
        for m in mots_fr + mots_ar:
            mn = normaliser(m)
            pos = chercher(z, mn)
            if pos is not None:
                candidats.append((pos, -len(mn), nom, nom_ar))
    if candidats:
        _, _, nom, nom_ar = min(candidats)
        return nom, nom_ar
    return None


def type_du_document(texte: str, texte_titre: str = ""):
    """On cherche dans le haut de la page (lecture spéciale du titre + premières lignes),
    puis dans tout le texte.
    - un mot-clé lu EXACTEMENT passe avant un mot-clé lu avec une petite erreur ;
    - le mot-clé qui apparaît EN PREMIER gagne : « Demande de certificat » est une demande ;
    - à position égale, le plus long (le plus précis) gagne."""
    haut = texte_titre + "\n" + "\n".join(texte.splitlines()[:6])
    for zone in (haut, texte):
        for chercher in (_exact, _approche):
            trouve = _meilleur_type(zone, chercher)
            if trouve:
                return trouve
    return "Autre", "أخرى"


# ---------- Titre et montant ----------

def titre_du_document(texte: str, type_doc: str, type_ar: str = ""):
    """La ligne qui contient le type (souvent en majuscules) sert de titre."""
    lignes = [l.strip() for l in texte.splitlines() if len(l.strip()) > 3]
    cibles = [normaliser(type_doc.split()[0])] + ([normaliser(type_ar.split()[0])] if type_ar else [])
    # 1) le mot du type écrit correctement, n'importe où dans la page
    for l in lignes:
        nl = normaliser(l).replace(" ", "")
        if any(c in nl for c in cibles):
            return l
    # 2) sinon, le mot lu avec une petite erreur d'OCR, dans le haut de la page
    for l in lignes[:40]:
        nl = normaliser(l).replace(" ", "")
        if any(len(c) >= 4 and fuzz.partial_ratio(c, nl) >= 85 for c in cibles):
            return l
    return lignes[0] if lignes else type_doc


NOMBRE = r"(\d{1,3}(?:[ .]\d{3})+|\d+)"
RE_TOTAL = re.compile(r"(?:total|المجموع)[^\d\n]{0,25}" + NOMBRE, re.IGNORECASE)
RE_MONTANT = re.compile(r"(?:montant|somme|مبلغ)[^\d\n]{0,25}" + NOMBRE, re.IGNORECASE)


def montant_total(texte: str):
    """Le montant du document : d'abord une ligne « TOTAL », sinon « Montant : ... ».
    On reste sur la même ligne, pour ne pas prendre un chiffre d'une autre ligne."""
    t = texte.translate(CHIFFRES_ARABES)
    for motif in (RE_TOTAL, RE_MONTANT):
        m = motif.search(t)
        if m:
            valeur = int(re.sub(r"[ .]", "", m.group(1)))
            if valeur >= 100:  # on ignore les petits nombres (quantités, numéros)
                return valeur
    return None


def extraire(texte: str, texte_titre: str = ""):
    type_doc, type_ar = type_du_document(texte, texte_titre)
    d = date_du_document(texte)
    return {
        "type": type_doc,
        "type_ar": type_ar,
        "titre": titre_du_document(texte_titre + "\n" + texte, type_doc, type_ar),
        "date": d.isoformat() if d else None,
        "annee": d.year if d else None,
        "montant": montant_total(texte),
    }