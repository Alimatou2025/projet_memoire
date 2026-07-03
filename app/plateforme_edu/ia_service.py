import os
import requests
import chromadb
from pypdf import PdfReader
from django.conf import settings

DOSSIER_DB = os.path.join(settings.BASE_DIR, "chroma_db_storage")
client_db = chromadb.PersistentClient(path=DOSSIER_DB)
collection = client_db.get_or_create_collection(name="cours_universite")

URL_OLLAMA = "http://ollama:11434"

def _convertir_en_chiffres(texte):
    url = f"{URL_OLLAMA}/api/embeddings"
    donnees = {"model": "nomic-embed-text", "prompt": texte}
    try:
        reponse = requests.post(url, json=donnees, timeout=30)
        if reponse.status_code == 200:
            return reponse.json().get("embedding")
    except Exception:
        return None

def lire_et_enregistrer_pdf(id_document, chemin_pdf):
    texte_complet = ""
    try:
        lecteur = PdfReader(chemin_pdf)
        for page in lecteur.pages:
            texte_page = page.extract_text()
            if texte_page:
                texte_complet += texte_page + "\n"
    except Exception as e:
        print(f"Impossible de lire le PDF dans Docker : {e}")
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
        return "L assistant IA est indisponible pour le moment."

    filtre = {"id_doc": str(id_document_filtre)} if id_document_filtre else None

    recherche = collection.query(
        query_embeddings=[vecteur_question],
        n_results=2,
        where=filtre
    )
    
    if recherche and recherche["documents"] and recherche["documents"][0]:
        contexte = "\n---\n".join(recherche["documents"][0])
    else:
        contexte = "Aucun document trouvé pour répondre."

    prompt = f"""Tu es un assistant pedagogique. Reponds a la question en utilisant UNIQUEMENT les informations du contexte fourni. Si la reponse n est pas dedans, dis poliment que tu ne sais pas.

Contexte :
{contexte}

Question : {question}
Reponse en francais :"""

    url_ia = f"{URL_OLLAMA}/api/generate"
    donnees_ia = {
        "model": "qwen2.5-coder:3b", 
        "prompt": prompt,
        "stream": False
    }
    
    try:
        reponse = requests.post(url_ia, json=donnees_ia, timeout=60)
        if reponse.status_code == 200:
            return reponse.json().get("response")
    except Exception as e:
        return f"Erreur de communication avec l IA dans Docker : {e}"
        
    return "Une erreur est survenue."

