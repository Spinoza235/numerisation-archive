"""
generer_documents.py — Crée 20 documents FICTIFS (français et arabe) pour la démo.

Chaque document est dessiné comme une vraie page, puis "abîmé" pour ressembler
à un scan de travers ou à une photo prise au téléphone (fond, ombre, flou, bruit).
Les noms, sociétés et montants sont inventés. Chaque page porte la mention
"Document fictif – démonstration".

Lancement :  python generer_documents.py
Résultat  :  documents/doc_01.jpg ... documents/doc_20.jpg
"""
import math
import random

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, features

from config import DOSSIER_DOCUMENTS, DOSSIER_POLICES

random.seed(7)
np.random.seed(7)

L, H = 1240, 1754  # page A4 à 150 dpi
MARGE = 110
RAQM = features.check("raqm")  # mise en forme native de l'arabe


def police(nom, taille):
    return ImageFont.truetype(str(DOSSIER_POLICES / nom), taille)


POLICES = {
    "fr": {"titre": police("DejaVuSerif-Bold.ttf", 46), "gras": police("DejaVuSerif-Bold.ttf", 28),
           "texte": police("DejaVuSerif.ttf", 27), "petit": police("DejaVuSans.ttf", 21)},
    "ar": {"titre": police("Amiri-Bold.ttf", 58), "gras": police("Amiri-Bold.ttf", 36),
           "texte": police("Amiri-Regular.ttf", 36), "petit": police("Amiri-Regular.ttf", 27)},
}


def forme_arabe(texte):
    """Sans libraqm, on met en forme l'arabe avec arabic_reshaper + bidi."""
    if RAQM:
        return texte
    import arabic_reshaper
    from bidi.algorithm import get_display
    return get_display(arabic_reshaper.reshape(texte))


def largeur(draw, texte, f, rtl):
    if rtl and RAQM:
        return draw.textlength(texte, font=f, direction="rtl", language="ar")
    return draw.textlength(forme_arabe(texte) if rtl else texte, font=f)


def ecrire(draw, x, y, texte, f, rtl, fill=(25, 25, 30)):
    if rtl:
        w = largeur(draw, texte, f, True)
        if RAQM:
            draw.text((x - w, y), texte, font=f, fill=fill, direction="rtl", language="ar")
        else:
            draw.text((x - w, y), forme_arabe(texte), font=f, fill=fill)
    else:
        draw.text((x, y), texte, font=f, fill=fill)


def couper(draw, texte, f, rtl, max_w):
    lignes, ligne = [], ""
    for mot in texte.split():
        essai = (ligne + " " + mot).strip()
        if largeur(draw, essai, f, rtl) <= max_w:
            ligne = essai
        else:
            lignes.append(ligne)
            ligne = mot
    if ligne:
        lignes.append(ligne)
    return lignes


def dessiner_page(doc):
    """doc = {"langue": "fr"|"ar", "blocs": [(type, contenu), ...]}"""
    rtl = doc["langue"] == "ar"
    P = POLICES[doc["langue"]]
    page = Image.new("RGB", (L, H), (252, 251, 247))
    d = ImageDraw.Draw(page)
    x_debut = L - MARGE if rtl else MARGE
    y = 90
    largeur_utile = L - 2 * MARGE

    for type_bloc, contenu in doc["blocs"]:
        if type_bloc == "entete":
            for i, ligne in enumerate(contenu):
                ecrire(d, x_debut, y, ligne, P["gras"] if i == 0 else P["petit"], rtl)
                y += 44 if i == 0 else 32
            y += 10
            d.line([(MARGE, y), (L - MARGE, y)], fill=(60, 60, 70), width=3)
            y += 50
        elif type_bloc == "titre":
            w = largeur(d, contenu, P["titre"], rtl)
            cx = (L - w) / 2
            ecrire(d, cx + w if rtl else cx, y, contenu, P["titre"], rtl)
            y += 110
        elif type_bloc == "para":
            for ligne in couper(d, contenu, P["texte"], rtl, largeur_utile):
                ecrire(d, x_debut, y, ligne, P["texte"], rtl)
                y += 46 if rtl else 40
            y += 26
        elif type_bloc == "tableau":
            col = [0.0, 0.55, 0.72, 1.0]
            for r, ligne in enumerate(contenu):
                f = P["gras"] if r == 0 else P["texte"]
                for c, cellule in enumerate(ligne):
                    if rtl:
                        xc = L - MARGE - col[c] * largeur_utile - 10
                    else:
                        xc = MARGE + col[c] * largeur_utile + 10
                    ecrire(d, xc, y + 8, cellule, f, rtl)
                y += 54
                d.line([(MARGE, y), (L - MARGE, y)], fill=(150, 150, 150), width=1)
            y += 40
        elif type_bloc == "date":
            x = MARGE if rtl else L - MARGE - largeur(d, contenu, P["texte"], rtl)
            ecrire(d, x + (largeur(d, contenu, P["texte"], rtl) if rtl else 0), y, contenu, P["texte"], rtl)
            y += 90
        elif type_bloc == "signature":
            x = MARGE + 330 if rtl else L - MARGE - 330
            ecrire(d, x, y, contenu, P["gras"], rtl)
            # tampon rond
            cx, cy = (MARGE + 170, y + 120) if rtl else (L - MARGE - 170, y + 120)
            d.ellipse([cx - 90, cy - 90, cx + 90, cy + 90], outline=(40, 70, 160), width=4)
            d.ellipse([cx - 75, cy - 75, cx + 75, cy + 75], outline=(40, 70, 160), width=2)
            y += 260

    mention = "وثيقة وهمية – للعرض فقط" if rtl else "Document fictif – démonstration"
    w = largeur(d, mention, P["petit"], rtl)
    ecrire(d, (L + w) / 2 if rtl else (L - w) / 2, H - 70, mention, P["petit"], rtl, fill=(150, 150, 150))
    return page


def abimer(page, mode):
    """Transforme la page propre en scan de travers ("scan") ou en photo ("photo")."""
    img = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)

    if mode == "scan":
        angle = random.uniform(-3.5, 3.5)
        M = cv2.getRotationMatrix2D((L / 2, H / 2), angle, 1.0)
        img = cv2.warpAffine(img, M, (L, H), borderValue=(250, 250, 250))
        img = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    else:
        # la page posée sur une table, photographiée un peu de travers
        W2, H2 = int(L * 1.3), int(H * 1.22)
        fond = np.full((H2, W2, 3), random.choice([(70, 90, 120), (60, 70, 80), (95, 110, 130)]), np.uint8)
        fond = cv2.add(fond, np.random.randint(0, 25, fond.shape, dtype=np.uint8))
        src = np.float32([[0, 0], [L, 0], [L, H], [0, H]])
        ox, oy = (W2 - L) / 2, (H2 - H) / 2
        j = lambda: random.uniform(-45, 45)
        dst = np.float32([[ox + j(), oy + j()], [ox + L + j(), oy + j()],
                          [ox + L + j(), oy + H + j()], [ox + j(), oy + H + j()]])
        M = cv2.getPerspectiveTransform(src, dst)
        page_w = cv2.warpPerspective(img, M, (W2, H2))
        masque = cv2.warpPerspective(np.full((H, L), 255, np.uint8), M, (W2, H2))
        img = np.where(masque[..., None] > 0, page_w, fond)
        # ombre douce (lumière inégale)
        gx = np.linspace(random.uniform(0.75, 0.9), 1.0, W2)
        gy = np.linspace(1.0, random.uniform(0.8, 0.95), H2)
        img = (img * np.outer(gy, gx)[..., None]).clip(0, 255).astype(np.uint8)
        img = cv2.GaussianBlur(img, (3, 3), 0.8)

    bruit = np.random.normal(0, 6, img.shape)
    img = (img + bruit).clip(0, 255).astype(np.uint8)
    return img


def date_fr(j, m, a):
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
            "septembre", "octobre", "novembre", "décembre"]
    return f"{j} {mois[m - 1]} {a}"


def chiffres_ar(texte):
    return texte.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


def construire_documents():
    E_SAHEL = ["SAHEL DISTRIBUTION SARL", "Avenue Charles de Gaulle, N'Djamena (fictif)", "Tél. +235 00 00 00 01"]
    E_ECOLE = ["ÉCOLE PRIVÉE LES RÔNIERS", "Quartier Chagoua, N'Djamena (fictif)", "Tél. +235 00 00 00 02"]
    E_CHARI = ["CHARI BÂTIMENT SA", "Zone industrielle de Farcha (fictif)", "Tél. +235 00 00 00 03"]
    E_LAC = ["IMPRIMERIE DU LAC", "Rue 40, Moursal (fictif)", "Tél. +235 00 00 00 04"]
    E_ASSO = ["ASSOCIATION DES COMMERÇANTS DE MOURSAL", "Marché de Moursal (fictif)", ""]
    E_CLINIQUE = ["CLINIQUE ESPOIR", "Quartier Klemat (fictif)", "Tél. +235 00 00 00 05"]
    E_PHARMA = ["PHARMACIE DU MARCHÉ", "Grand Marché, N'Djamena (fictif)", "Tél. +235 00 00 00 06"]

    docs = [
        {"langue": "fr", "blocs": [("entete", E_SAHEL), ("titre", "FACTURE N° 2024-0315"),
            ("para", "Client : Ahmat Mahamat Saleh, Boutique Al-Amal, quartier Diguel."),
            ("tableau", [["Désignation", "Qté", "Montant"], ["Riz parfumé 25 kg", "4", "70 000"],
                         ["Huile végétale 5 L", "6", "45 000"], ["Sucre 50 kg", "1", "38 000"],
                         ["TOTAL (FCFA)", "", "153 000"]]),
            ("para", "Paiement à 30 jours. Merci de votre confiance."),
            ("date", f"N'Djamena, le 14/03/2024"), ("signature", "La comptabilité")]},
        {"langue": "fr", "blocs": [("entete", E_CHARI), ("titre", "ATTESTATION DE TRAVAIL"),
            ("para", "Je soussigné, directeur des ressources humaines de Chari Bâtiment SA, atteste que Madame Clarisse Néloum est employée dans notre société en qualité de technicienne en génie civil depuis le 1er mars 2019."),
            ("para", "La présente attestation lui est délivrée pour servir et valoir ce que de droit."),
            ("date", f"Fait à N'Djamena, le {date_fr(2, 2, 2023)}"), ("signature", "Le Directeur RH")]},
        {"langue": "fr", "blocs": [("entete", E_ECOLE), ("titre", "CERTIFICAT DE SCOLARITÉ"),
            ("para", "Le directeur de l'École privée Les Rôniers certifie que l'élève Fatimé Haroun, née le 4 mai 2014, est régulièrement inscrite en classe de CM2 pour l'année scolaire 2024-2025."),
            ("date", f"N'Djamena, le {date_fr(15, 9, 2024)}"), ("signature", "Le Directeur")]},
        {"langue": "fr", "blocs": [("entete", ["CONTRAT DE LOCATION", "Entre particuliers (fictif)", ""]),
            ("titre", "CONTRAT DE BAIL D'HABITATION"),
            ("para", "Entre Monsieur Moussa Brahim, propriétaire, ci-après le bailleur, et Monsieur Djimadoum Ngarlem, ci-après le locataire, il a été convenu ce qui suit."),
            ("para", "Article 1 : le bailleur loue au locataire une maison de trois pièces située au quartier Walia. Article 2 : le loyer mensuel est fixé à 85 000 FCFA, payable avant le 5 de chaque mois. Article 3 : le bail est conclu pour une durée d'un an renouvelable."),
            ("date", f"Fait à N'Djamena, le {date_fr(1, 6, 2022)}"), ("signature", "Les deux parties")]},
        {"langue": "fr", "blocs": [("entete", E_PHARMA), ("titre", "REÇU DE PAIEMENT N° 0457"),
            ("para", "Reçu de Madame Hawa Issa la somme de vingt-cinq mille francs CFA (25 000 FCFA) en règlement de sa commande de médicaments."),
            ("para", "Mode de paiement : Airtel Money."),
            ("date", "N'Djamena, le 07/11/2023"), ("signature", "La caissière")]},
        {"langue": "fr", "blocs": [("entete", E_ASSO), ("titre", "PROCÈS-VERBAL DE RÉUNION"),
            ("para", "L'an deux mille vingt-quatre, s'est tenue l'assemblée générale de l'Association des commerçants de Moursal, sous la présidence de Monsieur Ousmane Abdelkerim."),
            ("para", "Ordre du jour : 1) sécurité du marché ; 2) cotisations de l'année ; 3) divers. Après débat, l'assemblée a décidé de recruter deux gardiens de nuit et de fixer la cotisation mensuelle à 2 000 FCFA."),
            ("date", f"Moursal, le {date_fr(20, 1, 2024)}"), ("signature", "Le Secrétaire")]},
        {"langue": "fr", "blocs": [("entete", E_CLINIQUE), ("titre", "CONVOCATION"),
            ("para", "Monsieur Ousmane Abdelkerim est prié de se présenter le 05/05/2025 à 9 heures au service administratif de la Clinique Espoir pour un entretien de recrutement au poste d'agent comptable."),
            ("para", "Se munir d'une pièce d'identité et des diplômes originaux."),
            ("date", "N'Djamena, le 28/04/2025"), ("signature", "L'Administrateur")]},
        {"langue": "fr", "blocs": [("entete", ["Achta Abakar", "Quartier Ardep Djoumbal, N'Djamena (fictif)", "Tél. +235 00 00 00 07"]),
            ("titre", "DEMANDE D'EMPLOI"),
            ("para", "À Monsieur le Directeur de la Clinique Espoir. Objet : demande d'emploi au poste de secrétaire médicale."),
            ("para", "Monsieur le Directeur, titulaire d'un BTS en secrétariat de direction et forte de trois ans d'expérience, j'ai l'honneur de solliciter un poste de secrétaire médicale dans votre établissement. Veuillez agréer mes salutations distinguées."),
            ("date", f"N'Djamena, le {date_fr(18, 4, 2024)}"), ("signature", "Achta Abakar")]},
        {"langue": "fr", "blocs": [("entete", E_LAC), ("titre", "FACTURE N° IL-2024-112"),
            ("para", "Client : École privée Les Rôniers."),
            ("tableau", [["Désignation", "Qté", "Montant"], ["Cahiers 100 pages", "500", "100 000"],
                         ["Bulletins de notes", "300", "45 000"], ["TOTAL (FCFA)", "", "145 000"]]),
            ("date", "Moursal, le 30/09/2024"), ("signature", "Le Gérant")]},
        {"langue": "fr", "blocs": [("entete", E_SAHEL), ("titre", "ATTESTATION DE STAGE"),
            ("para", "Nous attestons que Monsieur Mahamat Nour Adoum, étudiant en informatique, a effectué un stage de trois mois au sein de notre service logistique, du 12 mai au 12 août 2025. Il a fait preuve de sérieux et de rigueur."),
            ("date", f"N'Djamena, le {date_fr(12, 8, 2025)}"), ("signature", "Le Directeur général")]},
        {"langue": "fr", "blocs": [("entete", E_PHARMA), ("titre", "BON DE COMMANDE N° BC-0089"),
            ("para", "Fournisseur : Sahel Distribution SARL."),
            ("tableau", [["Article", "Qté", "Montant"], ["Gants d'examen (boîte)", "40", "60 000"],
                         ["Alcool 70 % 1 L", "30", "45 000"], ["TOTAL (FCFA)", "", "105 000"]]),
            ("date", "N'Djamena, le 03/02/2025"), ("signature", "Le Pharmacien")]},
        {"langue": "fr", "blocs": [("entete", E_CHARI), ("titre", "NOTE DE SERVICE N° 14"),
            ("para", "À l'attention de tout le personnel. À compter du lundi 16 octobre 2023, les horaires de travail sur les chantiers sont fixés de 6 h 30 à 14 h 30 en raison de la chaleur. Le port du casque reste obligatoire."),
            ("date", f"N'Djamena, le {date_fr(10, 10, 2023)}"), ("signature", "La Direction")]},
        {"langue": "fr", "blocs": [("entete", ["CONTRAT DE PRESTATION DE SERVICES", "Document fictif", ""]),
            ("titre", "CONTRAT DE PRESTATION"),
            ("para", "Entre Sahel Distribution SARL, le client, et l'Atelier Numérique, le prestataire. Objet : création d'un logiciel de gestion de stock et formation de deux employés."),
            ("para", "Montant : 1 200 000 FCFA, payable en deux tranches. Délai de réalisation : deux mois à compter de la signature."),
            ("date", f"N'Djamena, le {date_fr(22, 7, 2025)}"), ("signature", "Les deux parties")]},
        # ---------- Documents en arabe ----------
        {"langue": "ar", "blocs": [("entete", ["شركة الساحل للتوزيع", "شارع شارل ديغول، انجمينا (وهمي)", ""]),
            ("titre", "شهادة عمل"),
            ("para", "يشهد مدير الموارد البشرية بشركة الساحل للتوزيع أن السيد أحمد محمد صالح يعمل لدى الشركة بصفة محاسب منذ سنة 2020."),
            ("para", "وقد سلمت له هذه الشهادة بناء على طلبه لاستعمالها فيما يسمح به القانون."),
            ("date", "انجمينا في 12/03/2024"), ("signature", "المدير")]},
        {"langue": "ar", "blocs": [("entete", ["مكتبة النور", "حي مرصال، انجمينا (وهمي)", ""]),
            ("titre", "فاتورة رقم 77"),
            ("para", "الزبونة: حواء عيسى"),
            ("tableau", [["البيان", "الكمية", "المبلغ"], ["كتب مدرسية", "10", "35000"],
                         ["أقلام", "50", "5000"], ["المجموع", "", "40000"]]),
            ("date", "انجمينا في 21 يونيو 2023"), ("signature", "المحاسب")]},
        {"langue": "ar", "blocs": [("entete", ["عقد إيجار", "بين الأفراد (وهمي)", ""]),
            ("titre", "عقد إيجار منزل"),
            ("para", "تم الاتفاق بين السيد موسى إبراهيم المؤجر والسيد عثمان عبد الكريم المستأجر على إيجار منزل بحي فرشة."),
            ("para", "قيمة الإيجار الشهري ستون ألف فرنك يدفع في بداية كل شهر ومدة العقد سنة واحدة قابلة للتجديد."),
            ("date", "حرر في انجمينا بتاريخ 1 يناير 2024"), ("signature", "الطرفان")]},
        {"langue": "ar", "blocs": [("entete", ["جمعية تجار السوق الكبير", "انجمينا (وهمي)", ""]),
            ("titre", "محضر اجتماع"),
            ("para", "اجتمع أعضاء جمعية تجار السوق الكبير برئاسة السيد إدريس آدم لمناقشة نظافة السوق وتنظيم مواقف السيارات."),
            ("para", "وقرر المجتمعون تخصيص يوم السبت للنظافة العامة وتعيين لجنة من خمسة أعضاء لمتابعة التنفيذ."),
            ("date", "انجمينا في 15 مارس 2025"), ("signature", "الأمين العام")]},
        {"langue": "ar", "blocs": [("entete", ["صيدلية السوق", "السوق الكبير، انجمينا (وهمي)", ""]),
            ("titre", "إيصال استلام"),
            ("para", "استلمنا من السيدة عائشة أبكر مبلغ خمسين ألف فرنك سيفا نقدا ثمنا لأدوية."),
            ("date", "انجمينا في 08/08/2024"), ("signature", "أمين الصندوق")]},
        {"langue": "ar", "blocs": [("entete", ["فاطمة هارون", "حي شاقوا، انجمينا (وهمي)", ""]),
            ("titre", "طلب شهادة مدرسية"),
            ("para", "إلى السيد مدير مدرسة الرونيي الخاصة. الموضوع: طلب شهادة مدرسية."),
            ("para", "أتشرف بأن ألتمس من سيادتكم منحي شهادة مدرسية لابنتي المسجلة في الصف الخامس وذلك لتقديمها إلى الإدارة. وتقبلوا فائق الاحترام."),
            ("date", "انجمينا في 2 سبتمبر 2025"), ("signature", "فاطمة هارون")]},
        {"langue": "ar", "blocs": [("entete", ["شركة شاري للبناء", "المنطقة الصناعية فرشة (وهمي)", ""]),
            ("titre", "شهادة تدريب"),
            ("para", "تشهد شركة شاري للبناء أن الطالب محمد نور آدم أجرى تدريبا ميدانيا لمدة شهرين في قسم الهندسة المدنية وأظهر جدية وانضباطا."),
            ("date", "انجمينا في 30 نوفمبر 2025"), ("signature", "المدير العام")]},
    ]
    return docs


def main():
    docs = construire_documents()
    for i, doc in enumerate(docs, start=1):
        page = dessiner_page(doc)
        mode = "photo" if i % 2 == 0 else "scan"
        img = abimer(page, mode)
        chemin = DOSSIER_DOCUMENTS / f"doc_{i:02d}.jpg"
        cv2.imwrite(str(chemin), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        print(f"{chemin.name}  ({doc['langue']}, {mode})")
    print(f"\n{len(docs)} documents créés dans {DOSSIER_DOCUMENTS}")


if __name__ == "__main__":
    main()
