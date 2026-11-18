# Archives intelligentes — Numérisation de documents FR / AR

Démo du service « Numérisation d'archives » : des documents **scannés ou photographiés**
sont redressés, lus en **français et en arabe**, classés automatiquement (type + date),
puis retrouvés **en quelques millisecondes** en tapant un nom ou un mot.

> Les 20 documents de la démo sont **entièrement fictifs** (noms, sociétés, montants).

## Ce que fait la démo

| Étape | Outil | Résultat |
|---|---|---|
| 1. Nettoyage | OpenCV | La feuille est repérée dans la photo, remise à plat, redressée, les ombres effacées |
| 2. Lecture (OCR) | Tesseract (fra + ara) | Le texte est lu ; la langue est choisie automatiquement |
| 3. Extraction | Règles + rapidfuzz | Date du document, type (facture, attestation, محضر…), montant total |
| 4. Recherche | Meilisearch | Recherche instantanée, tolérante aux fautes de frappe, filtres type / langue / année |
| 5. Interface | Streamlit | Recherche, aperçu avant / après, ajout de nouveaux documents |

Résultats mesurés sur les 20 documents de test : **type correct 20/20, date correcte 20/20**,
recherche en **2 à 10 ms**.

## Installation (Ubuntu)

```bash
# 1. Tesseract avec le français et l'arabe
sudo apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-ara

# 2. Les bibliothèques Python
pip install -r requirements.txt

# 3. Meilisearch (optionnel mais recommandé)
curl -L https://install.meilisearch.com | sh
```

Sur Windows : installez Tesseract depuis https://github.com/UB-Mannheim/tesseract/wiki
(cochez « French » et « Arabic » dans les langues), et Meilisearch depuis ses releases GitHub.

## Lancer la démo

```bash
./lancer.sh
```

ou à la main, dans trois terminaux :

```bash
./meilisearch --no-analytics          # 1. le moteur de recherche (optionnel)
python indexation.py                  # 2. traite les documents (une seule fois, ~1 min)
streamlit run app.py                  # 3. l'interface → http://localhost:8501
```

Sans Meilisearch, l'application utilise une **recherche locale** intégrée : la démo marche quand même.

## Ajouter vos propres documents

- Dans l'interface : onglet **« Ajouter un document »**, déposez une photo ou un scan.
- Ou copiez les images dans `documents/` puis relancez `python indexation.py`.

Pour recréer les 20 documents fictifs : `python generer_documents.py`.

## Structure

| Fichier | Rôle |
|---|---|
| `config.py` | Réglages (dossiers, moteur OCR, adresse Meilisearch) |
| `generer_documents.py` | Crée les 20 documents fictifs (scans de travers et photos) |
| `pretraitement.py` | Nettoyage de l'image avec OpenCV |
| `ocr.py` | Lecture du texte (Tesseract, ou PaddleOCR en option) |
| `extraction.py` | Date, type, titre et montant du document |
| `indexation.py` | Le pipeline complet + envoi dans Meilisearch |
| `recherche.py` | Recherche Meilisearch, ou recherche locale de secours |
| `app.py` | L'interface Streamlit |
| `documents/` | Les images d'origine |
| `donnees/` | Les images nettoyées et les fiches JSON (résultats) |

## Mettre la démo en ligne gratuitement (Streamlit Community Cloud)

1. Poussez le projet sur GitHub, **avec** le dossier `donnees/` (déjà traité).
2. Sur https://share.streamlit.io, créez une app à partir du dépôt, fichier `app.py`.
3. Le fichier `packages.txt` installe Tesseract (fra + ara) automatiquement.
4. Dans **Settings → Secrets** de l'app, ajoutez la ligne `MODE_PUBLIC = "1"`.
5. En ligne, sans Meilisearch, la recherche intégrée prend le relais (elle tolère aussi les fautes de frappe).

### Le mode public

Avec `MODE_PUBLIC=1`, l'application est prête à être montrée à tout le monde :

- un **guide de démarrage** en 6 étapes s'ouvre à la première visite (bouton « Revoir le guide » ensuite) ;
- des **exemples cliquables** sous la barre de recherche (« Clarise Nelom », « موسى »…) ;
- un visiteur peut ajouter jusqu'à **5 documents à ses propres archives temporaires** : il les retrouve
  dans la recherche (badge « Votre document »), mais ils ne sont jamais ajoutés aux archives communes,
  ne sont visibles par aucun autre visiteur, et sont effacés automatiquement après une heure ;
- le bouton « Réindexer » et le téléchargement des originaux sont masqués.

Pour tester ce mode sur votre PC : `MODE_PUBLIC=1 streamlit run app.py`

## Limites connues (à dire au client)

- **Pas d'écriture manuscrite** : l'OCR lit le texte imprimé.
- **L'arabe est lu moins bien que le français** (confiance ~75-85 % contre ~94 %) ; la recherche
  tolère ces erreurs, mais un texte arabe peut contenir des fautes de lecture.
- Les chiffres arabes-indiens (١٢٣) sont mal lus par Tesseract ; les chiffres 0-9 sont bien lus.
- Pour des milliers de pages : traitement par lots et serveur plus puissant (hors démo).

## Options

- **PaddleOCR** (souvent meilleur sur les photos difficiles) :
  `pip install paddleocr paddlepaddle`, puis lancez avec `MOTEUR_OCR=paddle`.
- **Clé Meilisearch** : `MEILI_MASTER_KEY=... ./meilisearch` et la même variable pour l'application.