import os
import requests
import chromadb

OLLAMA_API_URL = "http://ollama:11434/api/generate"
OLLAMA_EMBED_URL = "http://ollama:11434/api/embeddings"

CHROMA_DATA_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
chroma_client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)

collection = chroma_client.get_or_create_collection(
    name="cours_universite_v2",
    metadata={"hnsw:space": "cosine"}
)


def _convertir_en_chiffres(texte):
    payload = {
        "model": "nomic-embed-text:latest",
        "prompt": texte
    }
    try:
        response = requests.post(OLLAMA_EMBED_URL, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json().get("embedding", [])
        return []
    except Exception as e:
        print(f"Erreur d'embedding : {e}", flush=True)
        return []


def prechauffer_modele():
    """
    Préchauffe le modèle 1.5b en RAM au démarrage de Django.
    """
    payload = {
        "model": "qwen2.5:1.5b",
        "prompt": "Bonjour",
        "stream": False,
        "options": {
            "num_predict": 300
       }
    }

    try:
        requests.post(OLLAMA_API_URL, json=payload, timeout=120)
        print("✅ Modèle qwen2.5:1.5b préchauffé et chargé en RAM.", flush=True)
    except Exception as e:
        print(f"⚠️ Échec du préchauffage du modèle : {e}", flush=True)


def lire_et_enregistrer_pdf(doc_id, chemin_pdf, titre_cours="Document"):
    from pypdf import PdfReader

    reader = PdfReader(chemin_pdf)
    texte_complet = ""
    for page in reader.pages:
        contenu = page.extract_text()
        if contenu:
            texte_complet += contenu + "\n"

    taille_chunk = 500
    chunks = [texte_complet[i:i+taille_chunk] for i in range(0, len(texte_complet), taille_chunk)]

    documents = []
    embeddings = []
    metadatas = []
    ids = []

    for index, chunk in enumerate(chunks):
        vector = _convertir_en_chiffres(chunk)
        if vector:
            documents.append(chunk)
            embeddings.append(vector)
            metadatas.append({"document_id": str(doc_id), "titre": titre_cours})
            ids.append(f"doc_{doc_id}_chunk_{index}")

    if documents:
        collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
    return len(documents)


def poser_question_a_lia(question_utilisateur, historique_messages=None, doc_id=None, modele="qwen2.5:1.5b"):
    """
    Interrogation RAG + Qwen2.5 1.5B
    """
    if historique_messages is None:
        historique_messages = []

    question_nettoyee = question_utilisateur.strip().strip('"').strip("'")
    question_vector = _convertir_en_chiffres(question_nettoyee)
    contexte_texte = "Aucun document spécifique trouvé."
    
    if question_vector:
        where_clause = {"document_id": str(doc_id)} if doc_id else None

        results = collection.query(
            query_embeddings=[question_vector],
            n_results=3,
            where=where_clause
        )

        SEUIL_PERTINENCE = 0.37
        extraits_pertinents = []

        if results and "documents" in results and "distances" in results:
            docs = results["documents"][0]
            distances = results["distances"][0]

            for doc, distance in zip(docs, distances):
                if distance <= SEUIL_PERTINENCE:
                    extraits_pertinents.append(doc)

        if extraits_pertinents:
            contexte_texte = "\n---\n".join(extraits_pertinents)

    historique_formate = ""
    for msg in historique_messages[-4:]:
        role = "Étudiant" if msg.get("role") == "user" else "Assistant LIA"
        historique_formate += f"{role}: {msg.get('content')}\n"

    prompt_systeme = f"""Tu es LIA, un assistant pédagogique bienveillant et précis sur la plateforme MonEspace.

[HISTORIQUE DE LA CONVERSATION]
{historique_formate if historique_formate else "Début de la conversation."}

[CONTEXTE DU COURS PDF]
{contexte_texte}

[CONSIGNE]
Réponds à l'étudiant. Si la question fait référence au message précédent (ex: "explique-le"), utilise l'historique pour identifier le sujet principal.

Question de l'étudiant: {question_nettoyee}
Réponse de LIA:"""

    payload = {
        "model": modele,
        "prompt": prompt_systeme,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=120)
        if response.status_code == 200:
            return response.json().get("response", "Désolé, je n'ai pas pu générer de réponse.")
        return f"Erreur du service IA (Code {response.status_code})."
    except Exception as e:
        return f"Erreur de connexion avec Ollama (Docker) : {str(e)}"
