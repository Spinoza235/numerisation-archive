#!/usr/bin/env bash
# lancer.sh — Lance toute la démo : Meilisearch, indexation (si besoin), interface.
cd "$(dirname "$0")"

# 1. Meilisearch, s'il est installé (binaire ./meilisearch ou dans le PATH)
MEILI=""
if [ -x ./meilisearch ]; then MEILI=./meilisearch; elif command -v meilisearch >/dev/null; then MEILI=meilisearch; fi
if [ -n "$MEILI" ]; then
  if ! curl -s http://127.0.0.1:7700/health >/dev/null; then
    echo "Démarrage de Meilisearch..."
    $MEILI --no-analytics --db-path ./donnees/meili > ./donnees/meilisearch.log 2>&1 &
    sleep 2
  fi
else
  echo "Meilisearch non trouvé : la recherche locale sera utilisée."
fi

# 2. Indexation (traite les documents si ce n'est pas déjà fait, sinon réindexe vite)
if [ -z "$(ls -A donnees/fiches 2>/dev/null)" ]; then
  python indexation.py
else
  python -c "from recherche import Moteur; n = Moteur().reindexer_tout(); print(f'{n} documents indexés' if n else 'Recherche locale')"
fi

# 3. Interface
streamlit run app.py
