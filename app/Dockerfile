# Image de base
FROM python:3.11-slim

# Informations 
LABEL maintainer="asadia.dieme@etu.ussein.edu.sn"
LABEL description="Plateforme Éducative Hors-ligne - Mémoire L3"

# Installer des dépendances système nécessaires à Django et MySQL
# Installer les dépendances système nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Mettre à jour pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Créer un répertoire de travail
WORKDIR /app

# On copie d'abord le requirements.txt pour gagner du temps au build
COPY requirements.txt /app/

# Installer les dépendances (Django, etc.)
RUN pip install --no-cache-dir -r requirements.txt

# Copier TOUT ton projet Django dans le conteneur
COPY . /app/

# Exposer le port de l'application
EXPOSE 8000

# Lancement automatique du serveur Django
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
