"""
app.py — L'interface de démonstration (Streamlit).

Lancement :  streamlit run app.py
Puis ouvrez http://localhost:8501

Pour une démo publique (en ligne) : MODE_PUBLIC=1 streamlit run app.py
"""
import html
import tempfile
from datetime import date
from pathlib import Path

import streamlit as st

from config import DOSSIER_DOCUMENTS, DOSSIER_PROPRES, EXTENSIONS_IMAGES, MODE_PUBLIC, NOM_APPLICATION
from indexation import traiter_document
from recherche import Moteur, charger_fiches

st.set_page_config(page_title=NOM_APPLICATION, layout="wide")

st.markdown("""
<style>
mark { background: #7C3AED; color: #fff; padding: 0 3px; border-radius: 3px; }
.carte { border: 1px solid rgba(255,255,255,.08); background: #14141F; border-radius: 14px;
         padding: 16px 18px; margin-bottom: 4px; }
.carte h4 { margin: 0 0 6px 0; font-size: 1.05rem; }
.badge { display: inline-block; padding: 2px 10px; margin: 0 6px 6px 0; border-radius: 999px;
         font-size: .78rem; background: rgba(124,58,237,.18); color: #C4B5FD; border: 1px solid rgba(124,58,237,.35); }
.extrait { color: #B8B8C8; font-size: .9rem; line-height: 1.5; }
.rtl { direction: rtl; text-align: right; font-family: 'Noto Naskh Arabic', 'Amiri', serif; }
.chrono { color: #A78BFA; font-weight: 600; }
.etape { color: #A78BFA; font-size: .85rem; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; }
.astuce { border-left: 3px solid #7C3AED; background: rgba(124,58,237,.10); padding: 10px 14px;
          border-radius: 0 10px 10px 0; margin: 10px 0; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def moteur():
    return Moteur()


M = moteur()
FICHES = charger_fiches()

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

EXEMPLES = ["Clarise Nelom", "loyer", "facture 2024", "Moursal", "موسى", "حواء"]


def date_lisible(iso):
    if not iso:
        return "Date inconnue"
    d = date.fromisoformat(iso)
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def montant_lisible(v):
    return f"{v:,}".replace(",", " ") + " FCFA" if v else None


# =====================================================================
# Guide de première visite (comme l'accueil d'une application mobile)
# =====================================================================

ETAPES_GUIDE = [
    ("Bienvenue",
     "Cette démonstration transforme des **documents papier** (photos ou scans) en archives "
     "**numériques et cherchables**, en français et en arabe.\n\n"
     "Visite guidée en 6 étapes, 30 secondes.",
     "Les 20 documents de la démo sont entièrement fictifs."),
    ("Rechercher un document",
     "Tapez un **nom**, un **mot** ou un **type** de document dans la barre de recherche, puis appuyez sur **Entrée**. "
     "Le bon document s'affiche en quelques millisecondes.",
     "Même avec une faute de frappe : essayez « Clarise Nelom ». Vous pouvez aussi cliquer sur un exemple sous la barre."),
    ("En français et en arabe",
     "La recherche fonctionne aussi en **arabe**.",
     "Essayez « موسى » ou « حواء »."),
    ("Filtrer",
     "Dans la **colonne de gauche**, filtrez par **type** de document (facture, contrat…), par **langue** ou par **année**.",
     "Sur téléphone, ouvrez la colonne avec la petite flèche « > » en haut à gauche."),
    ("Voir le document avant / après",
     "Sous chaque résultat, cliquez sur **« Ouvrir le document »** : vous voyez la photo d'origine, "
     "la version **nettoyée et redressée** par l'IA, et tout le texte lu.",
     None),
    ("Testez avec votre propre document",
     "Onglet **« Ajouter un document »** : déposez la photo d'un document **imprimé** (facture, attestation, courrier…). "
     "L'IA le redresse, le lit et reconnaît son type et sa date en quelques secondes.",
     "N'envoyez pas de document personnel ou confidentiel. L'écriture manuscrite n'est pas lue."),
]


@st.dialog("Guide de démarrage", width="large")
def guide():
    i = st.session_state.get("etape_guide", 0)
    titre, texte, astuce = ETAPES_GUIDE[i]
    n = len(ETAPES_GUIDE)

    st.progress((i + 1) / n)
    st.markdown(f'<div class="etape">Étape {i + 1} sur {n}</div>', unsafe_allow_html=True)
    st.subheader(titre)
    st.markdown(texte)
    if astuce:
        st.markdown(f'<div class="astuce">{html.escape(astuce)}</div>', unsafe_allow_html=True)

    # Illustration de l'étape « avant / après » avec un vrai document de la démo
    if titre.startswith("Voir le document") and (DOSSIER_DOCUMENTS / "doc_04.jpg").exists():
        a, b = st.columns(2)
        a.image(str(DOSSIER_DOCUMENTS / "doc_04.jpg"), caption="Avant : photo de travers", width="stretch")
        b.image(str(DOSSIER_PROPRES / "doc_04.png"), caption="Après : nettoyée et redressée", width="stretch")

    c1, c2, c3 = st.columns([1, 1, 1])
    if c1.button("Passer le guide", key="guide_passer"):
        st.session_state.etape_guide = 0
        st.rerun()
    if i > 0 and c2.button("Précédent", key="guide_prec", width="stretch"):
        st.session_state.etape_guide = i - 1
        st.rerun(scope="fragment")
    if i < n - 1:
        if c3.button("Suivant", key="guide_suiv", type="primary", width="stretch"):
            st.session_state.etape_guide = i + 1
            st.rerun(scope="fragment")
    elif c3.button("Commencer", key="guide_fin", type="primary", width="stretch"):
        st.session_state.etape_guide = 0
        st.rerun()


# Le guide s'ouvre tout seul à la première visite seulement
if not st.session_state.get("guide_vu"):
    st.session_state.guide_vu = True
    guide()


# ---------- En-tête ----------

st.title(NOM_APPLICATION)
st.caption("Numérisation et recherche de documents en français et en arabe · "
           "tapez un nom, un mot ou un type : le bon document s'affiche en une seconde.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Documents", len(FICHES))
c2.metric("En français", sum(f["langue"] == "fr" for f in FICHES))
c3.metric("En arabe", sum(f["langue"] == "ar" for f in FICHES))
c4.metric("Moteur", "Meilisearch" if M.client else "Intégré")

# ---------- Colonne de gauche ----------

with st.sidebar:
    if st.button("Revoir le guide", width="stretch"):
        st.session_state.etape_guide = 0
        guide()
    st.header("Filtres")
    types_dispo = sorted({f["type"] for f in FICHES})
    types = st.multiselect("Type de document", types_dispo, placeholder="Tous les types")
    langue = st.radio("Langue", ["Toutes", "Français", "Arabe"], horizontal=True)
    annees_dispo = sorted({f["annee"] for f in FICHES if f.get("annee")})
    annees = None
    if len(annees_dispo) > 1:
        annees = st.slider("Années", annees_dispo[0], annees_dispo[-1], (annees_dispo[0], annees_dispo[-1]))
    if not MODE_PUBLIC:
        st.divider()
        if st.button("Réindexer tous les documents", help="Remet la recherche en accord avec le dossier donnees/"):
            n = M.reindexer_tout()
            st.success(f"{n} documents réindexés." if n else "Meilisearch n'est pas lancé : recherche locale utilisée.")

code_langue = {"Toutes": None, "Français": "fr", "Arabe": "ar"}[langue]
if annees and annees == (annees_dispo[0], annees_dispo[-1]):
    annees = None  # pas de filtre si toute la plage est sélectionnée


def badges_et_extrait(r):
    rtl = r.get("langue") == "ar"
    badges = [r.get("type", ""), date_lisible(r.get("date")),
              "Arabe" if rtl else "Français", montant_lisible(r.get("montant"))]
    return rtl, "".join(f'<span class="badge">{html.escape(b)}</span>' for b in badges if b)


def afficher_resultat(r):
    rtl, badges_html = badges_et_extrait(r)
    classe = "extrait rtl" if rtl else "extrait"
    titre = r.get("titre_surligne") or html.escape(r.get("titre", ""))
    extrait = (r.get("extrait") or html.escape(r.get("texte", "")[:220])).replace("\n", " ")

    col_img, col_txt = st.columns([1, 5])
    image_propre = DOSSIER_PROPRES / f"{r['id']}.png"
    if image_propre.exists():
        col_img.image(str(image_propre), width="stretch")
    col_txt.markdown(
        f'<div class="carte"><h4 class="{"rtl" if rtl else ""}">{titre}</h4>{badges_html}'
        f'<div class="{classe}">{extrait}</div></div>', unsafe_allow_html=True)

    with col_txt.expander("Ouvrir le document"):
        afficher_detail(r, DOSSIER_DOCUMENTS / r["fichier"], image_propre, cle=r["id"])


def afficher_detail(r, origine: Path, image_propre: Path, cle: str):
    rtl = r.get("langue") == "ar"
    classe = "extrait rtl" if rtl else "extrait"
    a, b = st.columns(2)
    if origine.exists():
        a.image(str(origine), caption="Image d'origine (scan ou photo)", width="stretch")
    if image_propre.exists():
        b.image(str(image_propre), caption="Après nettoyage (redressée, sans ombre)", width="stretch")
    st.markdown("**Texte lu par l'OCR**")
    st.markdown(f'<div class="{classe}" style="white-space:pre-wrap">{html.escape(r.get("texte", ""))}</div>',
                unsafe_allow_html=True)
    st.caption(f"Confiance de lecture : {r.get('confiance_ocr', '—')} % · "
               f"inclinaison corrigée : {r.get('angle_corrige', 0)}° · "
               f"perspective corrigée : {'oui' if r.get('perspective_corrigee') else 'non'}")
    if origine.exists() and not MODE_PUBLIC:
        st.download_button("Télécharger l'original", origine.read_bytes(), file_name=r["fichier"], key=f"dl_{cle}")


onglet_recherche, onglet_ajout, onglet_explication = st.tabs(
    ["Rechercher", "Ajouter un document", "Comment ça marche"])

# ---------- Recherche ----------


def choisir_exemple(exemple):
    st.session_state.requete = exemple


with onglet_recherche:
    requete = st.text_input("Rechercher", key="requete", label_visibility="collapsed",
                            placeholder="Ex. : Clarisse, loyer, facture 2024, حواء, موسى…")
    st.caption("Essayez :")
    colonnes = st.columns(len(EXEMPLES))
    for col, exemple in zip(colonnes, EXEMPLES):
        col.button(exemple, key=f"ex_{exemple}", on_click=choisir_exemple, args=(exemple,), width="stretch")

    resultats, ms = M.rechercher(requete.strip(), types=types or None, langue=code_langue, annees=annees)
    st.markdown(f'<span class="chrono">{len(resultats)} document(s) trouvé(s) en {ms:.0f} ms</span>'
                f' · moteur : {M.nom}', unsafe_allow_html=True)
    if not resultats:
        st.info("Aucun document ne correspond. Essayez un autre mot ou retirez des filtres.")
    for r in resultats:
        afficher_resultat(r)

# ---------- Ajout ----------

with onglet_ajout:
    if MODE_PUBLIC:
        st.write("Déposez la photo d'un document **imprimé** : elle est nettoyée, lue et analysée en quelques secondes.")
        st.markdown('<div class="astuce">Démo publique : votre document est analysé pour vous seul, '
                    'puis effacé. Il n\'est ni conservé ni visible par les autres visiteurs. '
                    'Évitez tout de même les documents personnels ou confidentiels.</div>', unsafe_allow_html=True)
    else:
        st.write("Déposez une photo ou un scan : il est nettoyé, lu, classé et rendu cherchable en quelques secondes.")

    fichiers = st.file_uploader("Images de documents", type=[e.strip(".") for e in EXTENSIONS_IMAGES],
                                accept_multiple_files=not MODE_PUBLIC)
    if fichiers and not isinstance(fichiers, list):
        fichiers = [fichiers]

    if fichiers and st.button("Analyser" if MODE_PUBLIC else "Traiter les documents", type="primary"):
        nouvelles = []
        for f in fichiers:
            dossier_tmp = Path(tempfile.mkdtemp()) if MODE_PUBLIC else None
            chemin = (dossier_tmp or DOSSIER_DOCUMENTS) / f.name
            chemin.write_bytes(f.getbuffer())
            with st.status(f"Traitement de {f.name}…", expanded=False) as statut:
                st.write("1. Nettoyage de l'image (OpenCV)")
                st.write("2. Lecture du texte (OCR français / arabe)")
                st.write("3. Extraction de la date et du type")
                try:
                    if MODE_PUBLIC:
                        fiche = traiter_document(chemin, enregistrer=False, dossier_propres=dossier_tmp)
                    else:
                        fiche = traiter_document(chemin)
                except Exception as e:
                    statut.update(label=f"{f.name} : erreur ({e})", state="error")
                    continue
                statut.update(label=f"{f.name} : {fiche['type']} du {date_lisible(fiche['date'])} "
                                    f"({fiche['duree_traitement_s']} s)", state="complete")

            if MODE_PUBLIC:
                # Résultat montré à ce visiteur seulement
                rtl, badges_html = badges_et_extrait(fiche)
                st.markdown(f'<div class="carte"><h4 class="{"rtl" if rtl else ""}">'
                            f'{html.escape(fiche.get("titre", ""))}</h4>{badges_html}</div>', unsafe_allow_html=True)
                afficher_detail(fiche, chemin, Path(fiche["image_propre"]), cle=f"pub_{fiche['id']}")
                for p in dossier_tmp.iterdir():  # on efface tout de suite
                    p.unlink()
                dossier_tmp.rmdir()
            else:
                nouvelles.append(fiche)

        if nouvelles:
            try:
                M.ajouter([{k: v for k, v in f.items() if k != "texte_normalise"} for f in nouvelles])
            except RuntimeError as e:
                st.error(f"Le document est traité mais n'a pas pu être indexé : {e}")
            else:
                st.success(f"{len(nouvelles)} document(s) ajouté(s). Ils sont déjà cherchables dans l'onglet Rechercher.")

# ---------- Explication ----------

with onglet_explication:
    st.markdown("""
**1. Nettoyage de l'image** (OpenCV) : la feuille est repérée dans la photo et remise à plat,
le texte penché est redressé, les ombres sont effacées.

**2. Lecture du texte** (OCR Tesseract) : la page est lue en français et en arabe ;
le système garde automatiquement la langue la mieux lue.

**3. Extraction des informations** : la date du document, son type (facture, attestation,
contrat, محضر, إيصال…) et le montant total sont retrouvés automatiquement.

**4. Recherche instantanée** (Meilisearch) : chaque document devient cherchable par n'importe quel
mot, même avec une faute de frappe, en quelques millisecondes.

*Les documents de cette démonstration sont entièrement fictifs.*
""")