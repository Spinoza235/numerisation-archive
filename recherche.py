"""
recherche.py — Le moteur de recherche.

- Meilisearch (recommandé) : très rapide, tolère les fautes de frappe, gère l'arabe.
  Il tourne comme un petit serveur sur votre PC (voir README).
- Si Meilisearch n'est pas lancé, une recherche locale simple prend le relais,
  pour que la démo marche toujours.
"""
import html
import json
import re
import time

from config import DOSSIER_FICHES, MEILI_CLE, MEILI_INDEX, MEILI_URL
from rapidfuzz.distance import Levenshtein

from extraction import ARABE, normaliser

PARAMETRES_MEILI = {
    "searchableAttributes": ["titre", "texte", "texte_haut", "type", "type_ar", "fichier"],
    "filterableAttributes": ["type", "langue", "annee"],
    "sortableAttributes": ["date"],
    "displayedAttributes": ["*"],
}


def charger_fiches():
    fiches = []
    for f in sorted(DOSSIER_FICHES.glob("*.json")):
        fiches.append(json.loads(f.read_text(encoding="utf-8")))
    return fiches


class Moteur:
    def __init__(self):
        self.client = None
        self.nom = "recherche locale"
        try:
            import meilisearch
            client = meilisearch.Client(MEILI_URL, MEILI_CLE or None)
            client.health()
            self.client = client
            self.index = client.index(MEILI_INDEX)
            self.nom = "Meilisearch"
        except Exception:
            pass  # Meilisearch absent : on reste en recherche locale

    # ----- Indexation -----

    def preparer_index(self):
        if not self.client:
            return
        tache = self.client.create_index(MEILI_INDEX, {"primaryKey": "id"})
        self.client.wait_for_task(tache.task_uid)
        tache = self.index.update_settings(PARAMETRES_MEILI)
        self.client.wait_for_task(tache.task_uid)

    def ajouter(self, fiches):
        """Envoie les fiches à Meilisearch. Lève une erreur claire si Meilisearch refuse."""
        if not self.client or not fiches:
            return
        tache = self.index.add_documents(fiches)
        resultat = self.client.wait_for_task(tache.task_uid)
        if resultat.status != "succeeded":
            message = (resultat.error or {}).get("message", "erreur inconnue")
            raise RuntimeError(f"Meilisearch a refusé les documents : {message}")

    def reindexer_tout(self):
        """Remet l'index exactement en accord avec le dossier donnees/fiches :
        on vide l'index, puis on renvoie toutes les fiches. Un document supprimé
        du dossier disparaît donc aussi de la recherche."""
        if not self.client:
            return 0
        self.preparer_index()
        tache = self.index.delete_all_documents()
        self.client.wait_for_task(tache.task_uid)
        fiches = charger_fiches()
        self.ajouter(fiches)
        return len(fiches)

    # ----- Recherche -----

    def rechercher(self, requete, types=None, langue=None, annees=None, limite=20, fiches_visiteur=None):
        """Renvoie (resultats, temps_ms). Chaque résultat = la fiche + 'extrait' surligné.
        fiches_visiteur : documents ajoutés par un visiteur (mode public), cherchés en plus
        et affichés en premier. Ils ne sont jamais envoyés dans l'index commun."""
        debut = time.perf_counter()
        perso = []
        if fiches_visiteur:
            perso = self._local(requete, types, langue, annees, limite, fiches=fiches_visiteur)
        if self.client:
            resultats = self._meili(requete, types, langue, annees, limite)
            # Meilisearch découpe mal certains mots arabes (ex. « موسى ») :
            # pour une requête en arabe, on complète avec la recherche locale.
            if ARABE.search(requete or ""):
                deja = {r["id"] for r in resultats}
                resultats += [r for r in self._local(requete, types, langue, annees, limite)
                              if r["id"] not in deja]
        else:
            resultats = self._local(requete, types, langue, annees, limite)
        return (perso + resultats)[:limite], (time.perf_counter() - debut) * 1000

    def _meili(self, requete, types, langue, annees, limite):
        filtres = []
        if types:
            filtres.append("type IN [" + ", ".join(json.dumps(t) for t in types) + "]")
        if langue:
            filtres.append(f"langue = {json.dumps(langue)}")
        if annees:
            filtres.append(f"annee {annees[0]} TO {annees[1]}")
        options = {
            "limit": limite,
            "matchingStrategy": "all",  # tous les mots de la requête doivent être présents
            "filter": " AND ".join(filtres) or None,
            "attributesToCrop": ["texte"],
            "cropLength": 28,
            "attributesToHighlight": ["texte", "titre"],
            "highlightPreTag": "<mark>",
            "highlightPostTag": "</mark>",
        }
        if not requete:
            options["sort"] = ["date:desc"]
        reponse = self.index.search(requete or "", {k: v for k, v in options.items() if v is not None})
        sortie = []
        for hit in reponse["hits"]:
            fiche = {k: v for k, v in hit.items() if not k.startswith("_")}
            fmt = hit.get("_formatted", {})
            fiche["extrait"] = fmt.get("texte", "")[:400]
            fiche["titre_surligne"] = fmt.get("titre", fiche.get("titre", ""))
            sortie.append(fiche)
        return sortie

    def _local(self, requete, types, langue, annees, limite, fiches=None):
        mots = [m for m in normaliser(requete or "").split() if m]
        sortie = []
        for fiche in (charger_fiches() if fiches is None else fiches):
            if types and fiche.get("type") not in types:
                continue
            if langue and fiche.get("langue") != langue:
                continue
            if annees and not (fiche.get("annee") and annees[0] <= fiche["annee"] <= annees[1]):
                continue
            contenu = normaliser(" ".join([fiche.get("titre", ""), fiche.get("texte", ""), fiche.get("texte_haut", ""),
                                           fiche.get("type", ""), fiche.get("type_ar", "")]))
            # Chaque mot de la requête doit être trouvé : tel quel, ou presque (faute de frappe)
            mots_doc = set(re.findall(r"\w+", contenu))
            trouves = [mot_proche(m, contenu, mots_doc) for m in mots]
            if not all(trouves):
                continue
            # un mot trouvé tel quel compte bien plus qu'un mot trouvé « presque »
            score = sum(contenu.count(t) * (10 if t == m else 1) for t, m in zip(trouves, mots))
            fiche = dict(fiche)
            fiche["extrait"] = extrait_local(fiche.get("texte", ""), trouves, (requete or "").split())
            fiche["titre_surligne"] = html.escape(fiche.get("titre", ""))
            sortie.append((score, fiche.get("date") or "", fiche))
        sortie.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [f for _, _, f in sortie[:limite]]


def mot_proche(mot, contenu, mots_doc):
    """Renvoie le mot du document qui correspond à `mot` (lui-même s'il est présent),
    ou None. Tolère 1 faute pour les mots de 4 à 7 lettres, 2 fautes au-delà
    (comme Meilisearch) : « clarise » trouve « clarisse », « nelom » trouve « neloum »."""
    if mot in contenu:
        return mot
    if len(mot) < 4 or any(c.isdigit() for c in mot):  # pas de tolérance sur les nombres (2024 ≠ 2023)
        return None
    fautes_max = 1 if len(mot) < 8 else 2
    candidats = [m for m in mots_doc if abs(len(m) - len(mot)) <= fautes_max
                 and Levenshtein.distance(mot, m) <= fautes_max]
    return min(candidats, key=lambda m: Levenshtein.distance(mot, m)) if candidats else None


def extrait_local(texte, mots, mots_originaux=(), largeur=160):
    """Un morceau de texte autour du premier mot trouvé, avec les mots surlignés."""
    plat = texte.replace("\n", " ")
    norm = normaliser(plat)
    pos = min((norm.find(m) for m in mots if norm.find(m) >= 0), default=0)
    debut = max(0, pos - largeur // 2)
    morceau = html.escape(plat[debut:debut + largeur])
    termes = {m.lower() for m in mots} | {m.lower() for m in mots_originaux}
    for m in sorted(termes, key=len, reverse=True):
        if m in ("mark", "<", ">"):
            continue
        # surlignage approximatif (insensible à la casse) sur le texte d'origine
        morceau = re.sub(f"({re.escape(m)})", r"<mark>\1</mark>", morceau, flags=re.IGNORECASE)
    return ("…" if debut else "") + morceau + "…"