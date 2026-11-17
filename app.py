"""
app.py — L'interface de démonstration (Streamlit).

Lancement :  streamlit run app.py
Puis ouvrez http://localhost:8501
"""
import html
from datetime import date

import streamlit as st

from config import DOSSIER_DOCUMENTS, DOSSIER_PROPRES, EXTENSIONS_IMAGES, NOM_APPLICATION, RACINE
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
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def moteur():
    return Moteur()


M = moteur()
FICHES = charger_fiches()

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def date_lisible(iso):
    if not iso:
        return "Date inconnue"
    d = date.fromisoformat(iso)
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def montant_lisible(v):
    return f"{v:,}".replace(",", " ") + " FCFA" if v else None


# ---------- En-tête ----------

st.title(NOM_APPLICATION)
st.caption("Numérisation et recherche de documents en français et en arabe · "
           "tapez un nom, un mot ou un type : le bon document s'affiche en une seconde.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Documents", len(FICHES))
c2.metric("En français", sum(f["langue"] == "fr" for f in FICHES))
c3.metric("En arabe", sum(f["langue"] == "ar" for f in FICHES))
c4.metric("Moteur", M.nom)

# ---------- Filtres ----------

with st.sidebar:
    st.header("Filtres")
    types_dispo = sorted({f["type"] for f in FICHES})
    types = st.multiselect("Type de document", types_dispo, placeholder="Tous les types")
    langue = st.radio("Langue", ["Toutes", "Français", "Arabe"], horizontal=True)
    annees_dispo = sorted({f["annee"] for f in FICHES if f.get("annee")})
    annees = None
    if len(annees_dispo) > 1:
        annees = st.slider("Années", annees_dispo[0], annees_dispo[-1], (annees_dispo[0], annees_dispo[-1]))
    st.divider()
    if st.button("Réindexer tous les documents", help="À faire si vous avez lancé Meilisearch après coup"):
        n = M.reindexer_tout()
        st.success(f"{n} documents réindexés." if n else "Meilisearch n'est pas lancé : recherche locale utilisée.")

code_langue = {"Toutes": None, "Français": "fr", "Arabe": "ar"}[langue]
if annees and annees == (annees_dispo[0], annees_dispo[-1]):
    annees = None  # pas de filtre si toute la plage est sélectionnée


def afficher_resultat(r):
    rtl = r.get("langue") == "ar"
    classe = "extrait rtl" if rtl else "extrait"
    badges = [r.get("type", ""), date_lisible(r.get("date")),
              "Arabe" if rtl else "Français", montant_lisible(r.get("montant"))]
    badges_html = "".join(f'<span class="badge">{html.escape(b)}</span>' for b in badges if b)
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
        a, b = st.columns(2)
        origine = DOSSIER_DOCUMENTS / r["fichier"]
        if origine.exists():
            a.image(str(origine), caption="Image d'origine (scan ou photo)", width="stretch")
        if image_propre.exists():
            b.image(str(image_propre), caption="Après nettoyage (redressée, sans ombre)", width="stretch")
        st.markdown("**Texte lu par l'OCR**")
        st.markdown(f'<div class="{classe}" style="white-space:pre-wrap">{html.escape(r.get("texte", ""))}</div>',
                    unsafe_allow_html=True)
        st.caption(f"Fichier : {r['fichier']} · confiance de lecture : {r.get('confiance_ocr', '—')} % · "
                   f"inclinaison corrigée : {r.get('angle_corrige', 0)}° · "
                   f"perspective corrigée : {'oui' if r.get('perspective_corrigee') else 'non'}")
        if origine.exists():
            st.download_button("Télécharger l'original", origine.read_bytes(), file_name=r["fichier"],
                               key=f"dl_{r['id']}")


onglet_recherche, onglet_ajout, onglet_explication = st.tabs(
    ["Rechercher", "Ajouter un document", "Comment ça marche"])

# ---------- Recherche ----------

with onglet_recherche:
    requete = st.text_input("Rechercher", placeholder="Ex. : Clarisse, loyer, facture 2024, حواء, موسى…",
                            label_visibility="collapsed")
    resultats, ms = M.rechercher(requete.strip(), types=types or None, langue=code_langue, annees=annees)
    st.markdown(f'<span class="chrono">{len(resultats)} document(s) trouvé(s) en {ms:.0f} ms</span>'
                f' · moteur : {M.nom}', unsafe_allow_html=True)
    if not resultats:
        st.info("Aucun document ne correspond. Essayez un autre mot ou retirez des filtres.")
    for r in resultats:
        afficher_resultat(r)

# ---------- Ajout ----------

with onglet_ajout:
    st.write("Déposez une photo ou un scan : il est nettoyé, lu, classé et rendu cherchable en quelques secondes.")
    fichiers = st.file_uploader("Images de documents", type=[e.strip(".") for e in EXTENSIONS_IMAGES],
                                accept_multiple_files=True)
    if fichiers and st.button("Traiter les documents", type="primary"):
        nouvelles = []
        for f in fichiers:
            chemin = DOSSIER_DOCUMENTS / f.name
            chemin.write_bytes(f.getbuffer())
            with st.status(f"Traitement de {f.name}…", expanded=False) as statut:
                st.write("1. Nettoyage de l'image (OpenCV)")
                st.write("2. Lecture du texte (OCR français / arabe)")
                st.write("3. Extraction de la date et du type")
                try:
                    fiche = traiter_document(chemin)
                except Exception as e:
                    statut.update(label=f"{f.name} : erreur ({e})", state="error")
                    continue
                nouvelles.append(fiche)
                statut.update(label=f"{f.name} : {fiche['type']} du {date_lisible(fiche['date'])} "
                                    f"({fiche['duree_traitement_s']} s)", state="complete")
        try:
            M.ajouter([{k: v for k, v in f.items() if k != "texte_normalise"} for f in nouvelles])
        except RuntimeError as e:
            st.error(f"Le document est traité mais n'a pas pu être indexé : {e}")
        else:
            if nouvelles:
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