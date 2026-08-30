import os
import re
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

# Un modèle par grande famille de matières, décidé automatiquement par le
# modèle "chef" (classifier_matiere) plutôt que par un choix manuel de
# l'étudiant.
MODELES_PAR_MATIERE = {
    "maths_pc_svt": "deepseek-r1:1.5b",    # raisonnement étape par étape
    "generation_resume": "gemma2:2b",      # généraliste, résumés (déjà présent sur le Pi)
    "histoire_geo": "qwen2.5:1.5b",        # déjà utilisé, connaissances générales
}
MODELE_PAR_DEFAUT = "qwen2.5:1.5b"


def modele_pour_matiere(matiere):
    return MODELES_PAR_MATIERE.get(matiere, MODELE_PAR_DEFAUT)


def deviner_matiere(question):
    """Classification heuristique très simple par mots-clés, utilisée en
    dernier recours (secours) si le classificateur par modèle échoue."""
    q = question.lower()
    mots_maths_pc_svt = [
        "calcul", "équation", "physique", "chimie", "svt", "biologie",
        "math", "algèbre", "géométrie", "formule", "réaction", "cellule",
        "force", "énergie", "vitesse", "molécule", "alcane", "atome",
    ]
    mots_histoire_geo = [
        "histoire", "guerre", "roi", "révolution", "siècle", "empire",
        "géographie", "climat", "pays", "carte", "continent", "capitale",
    ]
    if any(mot in q for mot in mots_maths_pc_svt):
        return "maths_pc_svt"
    if any(mot in q for mot in mots_histoire_geo):
        return "histoire_geo"
    return "generation_resume"


def classifier_matiere(texte):
    """Modèle "chef" : qwen2.5:1.5b (déjà chargé, rapide) décide automatiquement
    la matière plutôt qu'un choix manuel de l'étudiant. Se rabat sur la
    classification par mots-clés (deviner_matiere) si l'appel échoue ou si la
    réponse du modèle n'est pas un des 3 labels attendus — pour rester fiable
    même en cas de lenteur/erreur réseau sur le Pi."""
    extrait = texte.strip()[:300]
    prompt = f"""Classe ce texte dans UNE seule catégorie parmi : maths_pc_svt, generation_resume, histoire_geo.
- maths_pc_svt : mathématiques, physique, chimie, SVT/biologie
- histoire_geo : histoire, géographie
- generation_resume : tout le reste (résumé, discussion générale, autre matière)

Texte : "{extrait}"

Réponds UNIQUEMENT avec le label exact, rien d'autre."""

    payload = {
        "model": "qwen2.5:1.5b",
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 10, "temperature": 0}
    }
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=20)
        if response.status_code == 200:
            label = response.json().get("response", "").strip().lower()
            for matiere_valide in MODELES_PAR_MATIERE:
                if matiere_valide in label:
                    return matiere_valide
    except Exception as e:
        print(f"Erreur classification matière : {e}", flush=True)

    return deviner_matiere(texte)


def nettoyer_reponse_deepseek(texte):
    """deepseek-r1 génère un bloc <think>...</think> de raisonnement interne
    avant sa réponse finale. Utile pour la qualité du raisonnement, mais ne
    doit pas être montré tel quel à l'étudiant."""
    return re.sub(r"<think>.*?</think>", "", texte, flags=re.DOTALL).strip()


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
    """Préchauffe le modèle 1.5b en RAM au démarrage de Django."""
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


def extraire_texte_pdf(chemin_pdf):
    """Extraction pure du texte, sans embedding. Rapide, utilisée pour répondre
    immédiatement pendant que l'indexation complète tourne en arrière-plan."""
    from pypdf import PdfReader

    reader = PdfReader(chemin_pdf)
    texte_complet = ""
    for page in reader.pages:
        contenu = page.extract_text()
        if contenu:
            texte_complet += contenu + "\n"
    return texte_complet


def lire_et_enregistrer_pdf(doc_id, chemin_pdf, titre_cours="Document", matiere="generation_resume"):
    texte_complet = extraire_texte_pdf(chemin_pdf)

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
            metadatas.append({"document_id": str(doc_id), "titre": titre_cours, "matiere": matiere})
            ids.append(f"doc_{doc_id}_chunk_{index}")

    if documents:
        collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
    return len(documents)


def generer_titre_conversation(question_utilisateur):
    """Génère un titre court à partir de la première question (et du nom du
    document attaché, si présent — voir l'appel dans views.py)."""
    prompt = f"""Donne un titre court (3 à 5 mots) identifiant le SUJET précis de cet échange, comme un titre de conversation. Si un nom de document est mentionné, base le titre dessus plutôt que sur la question elle-même. Pas de ponctuation finale. Réponds UNIQUEMENT avec le titre, rien d'autre.
Échange : {question_utilisateur}
Titre :"""
    payload = {
        "model": "qwen2.5:1.5b",
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 20}
    }
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=30)
        if response.status_code == 200:
            titre = response.json().get("response", "").strip().strip('"').strip("'")
            return titre[:60] if titre else question_utilisateur[:40]
    except Exception:
        pass
    return question_utilisateur[:40]


def poser_question_a_lia(question_utilisateur, historique_messages=None, doc_id=None,
                          contexte_force=None, modele="qwen2.5:1.5b"):
    if historique_messages is None:
        historique_messages = []

    question_nettoyee = question_utilisateur.strip().strip('"').strip("'")
    contexte_texte = "Aucun document spécifique trouvé."

    if contexte_force:
        # Un PDF vient d'être attaché dans ce même message : on répond directement
        # avec son texte brut, sans attendre la fin de l'indexation vectorielle.
        # Coupe à la dernière fin de phrase avant la limite plutôt qu'en plein mot,
        # sinon le petit modèle interprète le texte cassé comme "corrompu" et décroche.
        LIMITE = 2500
        extrait = contexte_force[:LIMITE]
        derniere_coupure = max(extrait.rfind('. '), extrait.rfind('\n'))
        if derniere_coupure > LIMITE * 0.5:
            extrait = extrait[:derniere_coupure + 1]

        contexte_texte = (
            "Voici le début du document déposé par l'étudiant "
            "(c'est un extrait, le document peut continuer au-delà) :\n\n"
            f"{extrait}"
        )
    else:
        question_vector = _convertir_en_chiffres(question_nettoyee)

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

    if contexte_force:
        instruction_contexte = (
            "Résume en 3 à 5 phrases le contenu ci-dessus en citant les notions "
            "précises qui y apparaissent. Ne pose pas de question à l'étudiant."
        )
    else:
        instruction_contexte = (
            "Si la question fait référence au message précédent (ex: \"explique-le\"), "
            "utilise l'historique pour identifier le sujet principal."
        )

    prompt_systeme = f"""Tu es LIA, un assistant pédagogique bienveillant et précis sur la plateforme MonEspace.
[HISTORIQUE DE LA CONVERSATION]
{historique_formate if historique_formate else "Début de la conversation."}

[CONTEXTE DU COURS PDF]
{contexte_texte}

[CONSIGNE]
{instruction_contexte}

Question de l'étudiant: {question_nettoyee}
Réponse de LIA:"""

    payload = {
        "model": modele,
        "prompt": prompt_systeme,
        "stream": False,
        "options": {
            # deepseek-r1 réfléchit d'abord dans <think>...</think> avant sa
            # réponse finale : il lui faut nettement plus de tokens que les
            # autres modèles pour produire une réponse complète.
            "num_predict": 700 if modele.startswith("deepseek") else 350
        }
    }

    try:
        # Timeout remonté à 180s : sur ce Pi (4 cœurs, pas de GPU), une
        # indexation encore en cours en arrière-plan peut fortement ralentir
        # la génération en cours (contention CPU entre processus Ollama).
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=180)
        if response.status_code == 200:
            texte = response.json().get("response", "Désolé, je n'ai pas pu générer de réponse.")
            if modele.startswith("deepseek"):
                texte = nettoyer_reponse_deepseek(texte)
            return texte
        return f"Erreur du service IA (Code {response.status_code})."
    except Exception as e:
        return f"Erreur de connexion avec Ollama (Docker) : {str(e)}"
