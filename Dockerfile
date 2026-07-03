FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Installation des dépendances système indispensables pour compiler mysqlclient
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# On copie le fichier de dépendances et on l'installe
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# On copie le reste du projet Django
COPY . /app/