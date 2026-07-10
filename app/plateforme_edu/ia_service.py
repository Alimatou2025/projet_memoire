import os
import requests
import chromadb
from pypdf import PdfReader
from django.conf import settings

DOSSIER_DB = os.path.join(settings.BASE_DIR, "chroma_db_storage")
client_db = chromadb.PersistentClient(path=DOSSIER_DB)
collection = client_db.get_or_create_collection(name="cours_universite")

URL_OLLAMA = "http://ollama:11434"

def prechauffer_modele():
    """Charge le modèle en RAM au démarrage du serveur"""
    url = f"{URL_OLLAMA}/api/generate"
    donnees = {
        "model": "qwen2.5:0.5b",
        "prompt": "Bonjour",
        "stream": False
    }
    try:
        requests.post(url, json=donnees, timeout=None)
        print("✅ Modèle qwen2.5:0.5b chargé en RAM")
    except Exception as e:
        print(f"⚠️ Préchauffage échoué : {e}")

def _convertir_en_chiffres(texte):
    url = f"{URL_OLLAMA}/api/embeddings"
    donnees = {"model": "nomic-embed-text:latest", "prompt": texte}
    try:
        reponse = requests.post(url, json=donnees, timeout=None)
        if reponse.status_code == 200:
            return reponse.json().get("embedding")
    except Exception:
        return None

# ✅ REVOILÀ LA FONCTION MANQUANTE !
def lire_et_enregistrer_pdf(id_document, chemin_pdf):
    texte_complet = ""
    try:
        lecteur = PdfReader(chemin_pdf)
        for page in lecteur.pages:
            texte_page = page.extract_text()
            if texte_page:
                texte_complet += texte_page + "\n"
    except Exception as e:
        print(f"Impossible de lire le PDF : {e}")
        return False

    if not texte_complet.strip():
        return False

    morceaux = []
    taille = 1000
    avancee = 800
    debut = 0
    while debut < len(texte_complet):
        fin = debut + taille
        morceaux.append(texte_complet[debut:fin])
        debut += avancee

    for index, morceau in enumerate(morceaux):
        vecteur = _convertir_en_chiffres(morceau)
        if vecteur:
            collection.add(
                embeddings=[vecteur],
                documents=[morceau],
                metadatas=[{"id_doc": str(id_document)}],
                ids=[f"doc_{id_document}_partie_{index}"]
            )
    return True

def poser_question_a_lia(question, id_document_filtre=None):
    vecteur_question = _convertir_en_chiffres(question)
    if not vecteur_question:
        return "L'assistant IA est indisponible pour le moment."

    filtre = {"id_doc": str(id_document_filtre)} if id_document_filtre else None
    
    recherche = collection.query(
        query_embeddings=[vecteur_question],
        n_results=1,  # ⚡ On ne cherche qu'un seul morceau pour aller plus vite
        where=filtre
    )

    if recherche and recherche["documents"] and recherche["documents"][0]:
        contexte = recherche["documents"][0][0]
    else:
        contexte = "Aucun document trouvé."

    # 🎯 On donne une consigne STRICTE à Qwen d'être ultra-court (maximum 1 phrase)
    prompt = f"""Contexte: {contexte}
Question: {question}
Réponds en français en une seule phrase courte :"""

    url_ia = f"{URL_OLLAMA}/api/generate"
    donnees_ia = {
        "model": "qwen2.5:0.5b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 50  # ⚡ Limite stricte à 50 tokens pour générer la réponse en 5 secondes chrono !
        }
    }

    try:
        reponse = requests.post(url_ia, json=donnees_ia, timeout=None)
        if reponse.status_code == 200:
            return reponse.json().get("response")
    except Exception as e:
        return f"Erreur de communication : {e}"
    
    return "Une erreur est survenue."