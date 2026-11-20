# Image Docker de la démo publique (Render, ou tout hébergeur qui accepte Docker)
FROM python:3.12-slim

# Tesseract avec le français et l'arabe (+ petite bibliothèque utile à OpenCV)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-fra tesseract-ocr-ara libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Utilisateur sans droits d'administrateur (plus sûr)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    MODE_PUBLIC=1

WORKDIR /home/user/app
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt
COPY --chown=user . .

EXPOSE 8501
# L'hébergeur donne le port dans la variable PORT (Render : 10000) ; 8501 par défaut.
# enableXsrfProtection=false : évite l'erreur 403 à l'envoi de fichiers derrière un proxy.
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.enableXsrfProtection=false"]