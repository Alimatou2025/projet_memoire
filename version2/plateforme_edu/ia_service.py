# -*- coding: utf-8 -*-
"""
Service assistant IA : RAG (recherche de passages pertinents) + routage
multi-modèle, en s'appuyant sur Ollama en local (voir la synthèse des
choix techniques du mémoire, sections 3.2, 3.4 et 3.5).

Résumé du pipeline :
    1. Un document est découpé en segments de ~500 caractères.
    2. Chaque segment est transformé en vecteur (embedding) par
       nomic-embed-text et enregistré (modèle SegmentDocument).
    3. Pour une question, on calcule son embedding, on compare par
       similarité cosinus à chaque segment, on garde ceux sous le seuil
       de distance 0,37, et on prend les 3 plus proches.
    4. Un petit modèle (Qwen) route la question vers l'un des 3 modèles
       spécialisés (DeepSeek pour le raisonnement, Qwen pour les
       connaissances générales, Gemma pour les résumés), avec un filet
       de secours par mots-clés si le routage échoue.
    5. Le modèle choisi génère la réponse à partir de la question, des
       passages retrouvés et des derniers échanges de la conversation.
"""

import json
import math
import re
import urllib.error
import urllib.request

import chromadb

CHROMA_DATA_PATH = "/home/alimatou/Documents/projet_memoire/app/plateforme_edu/chroma_db"
chroma_client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)
collection = chroma_client.get_or_create_collection(
    name="cours_universite_v2",
    metadata={"hnsw:space": "cosine"}
)

OLLAMA_URL = "http://localhost:11434"

SEQUENCES_ARRET = ["\nQuestion :", "\nQuestion précédente :", "\nRéponse précédente :"]

MODELE_EMBEDDING = "nomic-embed-text"
MODELE_ROUTEUR = "qwen2.5:1.5b"
MODELES_PAR_CATEGORIE = {
    "raisonnement": "deepseek-r1:1.5b",
    "connaissances_generales": "qwen2.5:1.5b",
    "resume": "gemma2:2b",
}

TAILLE_SEGMENT = 800
SEUIL_DISTANCE = 0.50
NOMBRE_PASSAGES = 3

MAX_SEGMENTS_FICHIER_TEMPORAIRE = 40

MOTS_CLES_RESUME = ["résume", "résumé", "synthétise", "synthèse", "en bref", "en quelques mots"]
MOTS_CLES_RAISONNEMENT = ["pourquoi", "calcule", "résous", "démontre", "prouve", "raisonnement"]


class ErreurServiceIA(Exception):
    """Levée quand Ollama est injoignable ou répond de façon inattendue."""


def _appel_ollama(chemin, payload, timeout=90):
    donnees = json.dumps(payload).encode("utf-8")
    requete = urllib.request.Request(
        f"{OLLAMA_URL}{chemin}",
        data=donnees,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:
            return json.loads(reponse.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as erreur:
        raise ErreurServiceIA(
            "Impossible de contacter Ollama (vérifie que le conteneur tourne)."
        ) from erreur


def obtenir_embedding(texte):
    """Renvoie le vecteur (liste de 768 nombres) d'un texte via nomic-embed-text."""
    resultat = _appel_ollama("/api/embeddings", {"model": MODELE_EMBEDDING, "prompt": texte})
    return resultat.get("embedding", [])


def decouper_en_segments(texte, taille=TAILLE_SEGMENT):
    """Découpe un texte en segments de `taille` caractères (section 3.4.3 du mémoire)."""
    texte_normalise = re.sub(r"\s+", " ", texte or "").strip()
    return [
        texte_normalise[i:i + taille]
        for i in range(0, len(texte_normalise), taille)
        if texte_normalise[i:i + taille].strip()
    ]


def similarite_cosinus(vecteur_a, vecteur_b):
    produit_scalaire = sum(x * y for x, y in zip(vecteur_a, vecteur_b))
    norme_a = math.sqrt(sum(x * x for x in vecteur_a))
    norme_b = math.sqrt(sum(y * y for y in vecteur_b))
    if norme_a == 0 or norme_b == 0:
        return 0.0
    return produit_scalaire / (norme_a * norme_b)


def extraire_texte_pdf(fichier):
    """`fichier` : chemin (str) ou objet fichier ouvert en binaire (ex : UploadedFile)."""
    from pypdf import PdfReader

    lecteur = PdfReader(fichier)
    return "\n".join(page.extract_text() or "" for page in lecteur.pages)


def extraire_texte_fichier_televerse(fichier_televerse):
    """Extrait le texte d'un fichier envoyé via un formulaire (request.FILES)."""
    nom = (fichier_televerse.name or "").lower()
    fichier_televerse.seek(0)
    if nom.endswith(".pdf"):
        texte = extraire_texte_pdf(fichier_televerse)
    else:
        texte = fichier_televerse.read().decode("utf-8", errors="ignore")
    fichier_televerse.seek(0)
    return texte


def indexer_document(document):
    """
    Découpe le fichier d'un Document en segments, calcule leurs embeddings
    et les enregistre dans ChromaDB (collection partagée avec projet_memoire).
    """
    if not document.fichier:
        return

    document_id = str(document.ressource_id)

    anciens = collection.get(where={"document_id": document_id})
    if anciens["ids"]:
        collection.delete(ids=anciens["ids"])

    with document.fichier.open("rb") as fichier:
        if document.fichier.name.lower().endswith(".pdf"):
            texte = extraire_texte_pdf(fichier)
        else:
            texte = fichier.read().decode("utf-8", errors="ignore")

    segments = decouper_en_segments(texte)
    documents_txt, embeddings, metadatas, ids = [], [], [], []
    for index, segment in enumerate(segments):
        vecteur = obtenir_embedding(segment)
        if vecteur:
            documents_txt.append(segment)
            embeddings.append(vecteur)
            metadatas.append({
                "document_id": document_id,
                "titre": document.ressource.titre,
                "matiere": document.ressource.matiere or "generation_resume",
            })
            ids.append(f"doc_{document_id}_chunk_{index}")

    if documents_txt:
        collection.add(documents=documents_txt, embeddings=embeddings, metadatas=metadatas, ids=ids)

    document.indexe = True
    document.save(update_fields=["indexe"])
    return len(documents_txt)

    document.segments.all().delete()
    for position, segment in enumerate(decouper_en_segments(texte)):
        try:
            embedding = obtenir_embedding(segment)
        except ErreurServiceIA:
            continue
        if embedding:
            SegmentDocument.objects.create(
                document=document, texte=segment, embedding=embedding, ordre=position,
            )

    document.indexe = True
    document.save(update_fields=["indexe"])


def rechercher_passages_document(question, document, k=NOMBRE_PASSAGES, seuil_distance=SEUIL_DISTANCE):
    """Cherche les k passages les plus pertinents dans un Document précis (ChromaDB)."""
    embedding_question = obtenir_embedding(question)
    if not embedding_question:
        return []

    document_id = str(document.ressource_id)
    resultats = collection.query(
        query_embeddings=[embedding_question],
        n_results=k,
        where={"document_id": document_id},
    )

    passages = []
    if resultats and resultats.get("documents"):
        docs = resultats["documents"][0]
        distances = resultats["distances"][0]
        for texte, distance in zip(docs, distances):
            if distance <= seuil_distance:
                passages.append(texte)
    return passages


def rechercher_passages_corpus(question, k=NOMBRE_PASSAGES, seuil_distance=SEUIL_DISTANCE):
    """
    Cherche les k passages les plus pertinents dans TOUT le corpus ChromaDB,
    sans se limiter a un document precis (utilise quand l'apprenant pose une
    question sans selectionner de ressource au prealable).
    """
    embedding_question = obtenir_embedding(question)
    if not embedding_question:
        return []

    resultats = collection.query(
        query_embeddings=[embedding_question],
        n_results=k,
    )

    passages = []
    if resultats and resultats.get("documents"):
        docs = resultats["documents"][0]
        distances = resultats["distances"][0]
        for texte, distance in zip(docs, distances):
            if distance <= seuil_distance:
                passages.append(texte)
    return passages


def rechercher_passages_fichier_televerse(question, fichier_televerse, k=NOMBRE_PASSAGES, seuil_distance=SEUIL_DISTANCE):
    """
    Même principe, mais pour un fichier importé à la volée dans le chat
    (bouton « + »), sans l'enregistrer comme ressource permanente.
    """
    texte = extraire_texte_fichier_televerse(fichier_televerse)
    embedding_question = obtenir_embedding(question)
    if not embedding_question:
        return []

    segments = decouper_en_segments(texte)[:MAX_SEGMENTS_FICHIER_TEMPORAIRE]

    resultats = []
    for segment in segments:
        try:
            embedding_segment = obtenir_embedding(segment)
        except ErreurServiceIA:
            continue
        if not embedding_segment:
            continue
        distance = 1 - similarite_cosinus(embedding_question, embedding_segment)
        if distance <= seuil_distance:
            resultats.append((distance, segment))

    resultats.sort(key=lambda paire: paire[0])
    return [texte for _, texte in resultats[:k]]


def router_question(question):
    """
    Renvoie une clé de MODELES_PAR_CATEGORIE. Utilise un petit modèle Qwen
    pour comprendre le sens de la question ; si sa réponse ne peut pas être
    interprétée (ou si Ollama est injoignable), on retombe sur une règle de
    mots-clés simple, utilisée uniquement comme filet de secours.
    """
    prompt = (
        "Classe la question suivante dans une seule de ces trois catégories : "
        "raisonnement (calcul, logique, démonstration), "
        "connaissances_generales (fait, définition, cours), "
        "resume (demande de résumé ou de synthèse). "
        "Réponds uniquement par le mot de la catégorie, rien d'autre.\n\n"
        f"Question : {question}"
    )
    try:
        resultat = _appel_ollama(
            "/api/generate",
            {"model": MODELE_ROUTEUR, "prompt": prompt, "stream": False},
            timeout=30,
        )
        reponse_brute = resultat.get("response", "").strip().lower()
        for categorie in MODELES_PAR_CATEGORIE:
            if categorie in reponse_brute:
                return categorie
    except ErreurServiceIA:
        pass

    question_minuscule = question.lower()
    if any(mot in question_minuscule for mot in MOTS_CLES_RESUME):
        return "resume"
    if any(mot in question_minuscule for mot in MOTS_CLES_RAISONNEMENT):
        return "raisonnement"
    return "connaissances_generales"


def _nettoyer_reponse(texte):
    texte = re.sub(r"<think>.*?</think>", "", texte, flags=re.DOTALL).strip()
    texte = re.sub(r"\\\[|\\\]|\\\(|\\\)", "", texte)
    texte = re.sub(r"\\text\{([^}]*)\}", r"\1", texte)
    texte = re.sub(r"\\boxed\{([^}]*)\}", r"\1", texte)
    texte = re.sub(r"\\frac\{([^}]*)\}\{([^}]*)\}", r"(\1)/(\2)", texte)
    texte = re.sub(r"\\sqrt\{([^}]*)\}", r"√(\1)", texte)
    remplacements = {
        r"\\Delta": "Δ", r"\\alpha": "α", r"\\beta": "β", r"\\pi": "π",
        r"\\times": "×", r"\\cdot": "·", r"\\leq": "≤", r"\\geq": "≥",
        r"\\neq": "≠", r"\\infty": "∞",
    }
    for motif, symbole in remplacements.items():
        texte = re.sub(motif, symbole, texte)
    texte = re.sub(r"\*\*(.*?)\*\*", r"\1", texte)
    texte = re.sub(r"\*(.*?)\*", r"\1", texte)
    exposants = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
    indices = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    texte = re.sub(r"\^\{?(\d+)\}?", lambda m: m.group(1).translate(exposants), texte)
    texte = re.sub(r"_\{?(\d+)\}?", lambda m: m.group(1).translate(indices), texte)
    texte = re.sub(r"[ \t]+", " ", texte)
    return texte.strip()


def generer_reponse(question, passages=None, historique=None):
    """
    Route la question vers le bon modèle et génère la réponse, en
    s'appuyant sur les passages de cours fournis (le cas échéant) et sur
    les derniers échanges de la conversation (le cas échéant, pour les
    questions de suivi du type "et pour un cercle ?").
    `historique` : liste de tuples (question, reponse), du plus ancien
    au plus récent.
    Renvoie (texte_reponse, nom_du_modele_utilise).
    """
    categorie = router_question(question)
    modele = MODELES_PAR_CATEGORIE[categorie]

    bloc_historique = ""
    if historique:
        echanges_formates = "\n\n".join(
            f"Question précédente : {q}\nRéponse précédente : {r}"
            for q, r in historique
        )
        bloc_historique = (
            "Voici les derniers échanges de la conversation, pour comprendre "
            "le contexte si la question actuelle s'y réfère (ex : \"et pour un "
            "cercle ?\" après une question sur un triangle) :\n"
            f"{echanges_formates}\n\n"
        )

    if passages:
        contexte = "\n\n---\n\n".join(passages)
        prompt = (
            "Tu es un assistant pédagogique. Réponds à la question de l'apprenant "
            "en t'appuyant sur les extraits de cours ci-dessous. S'ils ne suffisent "
            "pas, tu peux compléter avec tes connaissances générales en le précisant.\n\n"
            f"{bloc_historique}"
            f"Extraits de cours :\n{contexte}\n\n"
            f"Question : {question}\n\nRéponse :"
        )
    else:
        prompt = (
            "Tu es un assistant pédagogique. Aucun document de cours pertinent "
            "n'a été trouvé pour cette question. Réponds directement et "
            "concrètement à la question, sans reformuler ni commenter la "
            "question elle-même. Si tu es raisonnablement sûr de ta réponse, "
            "donne-la ; signale explicitement ton incertitude sur les faits "
            "précis, dates, chiffres, formules ou noms propres plutôt que "
            "d'affirmer une réponse qui pourrait être fausse.\n\n"
            f"{bloc_historique}Question : {question}\n\nRéponse :"
        )

    try:
        resultat = _appel_ollama(
            "/api/generate",
            {
                "model": modele,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 1200 if modele.startswith("deepseek") else 350,
                    "stop": SEQUENCES_ARRET,
                },
            },
            timeout=240,
        )
        texte_reponse = _nettoyer_reponse(resultat.get("response", ""))
    except ErreurServiceIA:
        texte_reponse = (
            "Désolé, je n'ai pas pu contacter le service IA local (Ollama). "
            "Vérifie que le conteneur `memoire_ia` tourne bien."
        )

    return texte_reponse, modele
