import os
import re
import requests
import chromadb

# Adresses des services Ollama (qui fait tourner les modèles) à l'intérieur
# du réseau Docker. "ollama" c'est le nom du conteneur, pas une vraie adresse
# internet.
OLLAMA_API_URL = "http://ollama:11434/api/generate"
OLLAMA_EMBED_URL = "http://ollama:11434/api/embeddings"

# ChromaDB a besoin d'un dossier pour sauvegarder ses données sur le disque,
# sinon tout serait perdu à chaque redémarrage du conteneur.
CHROMA_DATA_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
chroma_client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)

# On crée (ou récupère si elle existe déjà) la "collection" où seront rangés
# tous les morceaux de cours vectorisés. Le paramètre hnsw:space=cosine dit
# à Chroma d'utiliser la similarité cosinus pour comparer les vecteurs entre
# eux (c'est la formule vue en cours, cos(theta) = A.B / (||A||*||B||)).
collection = chroma_client.get_or_create_collection(
    name="cours_universite_v2",
    metadata={"hnsw:space": "cosine"}
)

# Association matière -> modèle. C'est simplement un dictionnaire Python,
# donc quand on connaît la matière on retrouve le nom du modèle en une ligne.
MODELES_PAR_MATIERE = {
    "maths_pc_svt": "deepseek-r1:1.5b",
    "generation_resume": "gemma2:2b",
    "histoire_geo": "qwen2.5:1.5b",
}
MODELE_PAR_DEFAUT = "qwen2.5:1.5b"

# Petite liste de mots qui veulent dire "bonjour" en gros, pour éviter de
# lancer tout le système pour rien sur un simple message de politesse.
SALUTATIONS = {"cc", "coucou", "salut", "slt", "bonjour", "bonsoir", "hello", "hi", "yo", "bjr"}

# Ce texte sert de "valeur par défaut" pour dire qu'on n'a rien trouvé dans
# les cours. On le met dans une variable pour ne pas se tromper en le
# retapant à plusieurs endroits du fichier.
AUCUN_CONTEXTE = "Aucun document spécifique trouvé."

# Ce sont les mots du prompt système eux-mêmes. Si le modèle se met à les
# réécrire après sa vraie réponse, ça veut dire qu'il a recommencé un
# deuxième tour de dialogue tout seul, au lieu de s'arrêter — un signe
# qu'on utilise plus bas pour couper la réponse au bon endroit.
MARQUEURS_REPETITION = [
    "Question de l'étudiant", "Réponse de LIA", "Étudiant:", "Assistant LIA:",
]


def modele_pour_matiere(matiere):
    # .get() avec une valeur par défaut : si la matière n'existe pas dans le
    # dictionnaire (cas normalement impossible mais on sait jamais), on
    # renvoie qwen2.5 plutôt que de faire planter le programme.
    return MODELES_PAR_MATIERE.get(matiere, MODELE_PAR_DEFAUT)


def est_message_trop_court_pour_repondre(question):
    # On enlève les espaces au début/fin, on met tout en minuscule, et on
    # enlève aussi la ponctuation à la fin (genre "cc!" doit compter pareil
    # que "cc"). rstrip() enlève les caractères donnés SEULEMENT à la fin.
    q = question.strip().lower().rstrip("!?. ")

    # Si le message fait moins de 4 caractères, OU si c'est un mot de la
    # liste des salutations, on considère que c'est pas une vraie question.
    return len(q) < 4 or q in SALUTATIONS


def deviner_matiere(question):
    # Ça, c'est le plan B si jamais Qwen (le vrai classificateur) ne répond
    # pas à temps. On regarde juste si certains mots apparaissent dans la
    # question, un peu bête mais ça marche pour les cas simples.
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
    # any() renvoie True dès qu'au moins un mot de la liste est trouvé dans q
    if any(mot in q for mot in mots_maths_pc_svt):
        return "maths_pc_svt"
    if any(mot in q for mot in mots_histoire_geo):
        return "histoire_geo"
    return "generation_resume"


def classifier_matiere(texte):
    # On prend que les 300 premiers caractères, pas besoin de plus pour
    # deviner la matière, et ça évite de faire attendre Qwen pour rien.
    extrait = texte.strip()[:300]

    # Le prompt qu'on envoie à Qwen. On lui explique bien les 3 catégories
    # possibles, et on lui dit de répondre juste avec le mot, sans phrase
    # autour, pour pouvoir traiter sa réponse facilement après.
    prompt = f"""Classe ce texte dans UNE seule catégorie parmi : maths_pc_svt, generation_resume, histoire_geo.
- maths_pc_svt : mathématiques, physique, chimie, SVT/biologie
- histoire_geo : histoire, géographie
- generation_resume : tout le reste (résumé, discussion générale, autre matière)

Texte : "{extrait}"

Réponds UNIQUEMENT avec le label exact, rien d'autre."""

    # temperature=0 veut dire qu'on demande au modèle d'être le moins
    # "créatif" possible, pour qu'il réponde toujours pareil sur la même
    # question. num_predict=10 limite sa réponse à 10 tokens max, largement
    # suffisant pour un seul mot.
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
            # On vérifie que la réponse contient bien un des 3 labels
            # attendus, au cas où Qwen aurait ajouté un mot en trop.
            for matiere_valide in MODELES_PAR_MATIERE:
                if matiere_valide in label:
                    return matiere_valide
    except Exception as e:
        # Si ça plante (réseau coupé, timeout...), on n'arrête pas tout le
        # programme, on affiche juste l'erreur dans les logs pour debug.
        print(f"Erreur classification matière : {e}", flush=True)

    # Si on arrive ici, soit l'appel a raté, soit Qwen a donné une réponse
    # bizarre : dans les deux cas on se rabat sur la méthode par mots-clés.
    return deviner_matiere(texte)


def nettoyer_reponse_deepseek(texte):
    # DeepSeek écrit son "brouillon de réflexion" entre <think> et </think>
    # avant sa vraie réponse. On enlève ce bloc avec une regex, parce que
    # l'étudiant n'a pas besoin de voir ce raisonnement interne.
    # re.DOTALL fait que le "." de la regex attrape aussi les retours à la
    # ligne (sinon ça ne marcherait que sur une seule ligne).
    return re.sub(r"<think>.*?</think>", "", texte, flags=re.DOTALL).strip()


def tronquer_repetition(texte):
    # Filet de sécurité en plus du paramètre stop donné à Ollama : si le
    # modèle a quand même recommencé à halluciner un nouveau tour de
    # dialogue (en réécrivant "Réponse de LIA :" une deuxième fois par
    # exemple), on coupe la réponse pile à cet endroit, plutôt que de
    # laisser un texte dupliqué et incohérent s'afficher chez l'étudiant.
    position_min = len(texte)
    trouve = False
    for marqueur in MARQUEURS_REPETITION:
        index = texte.find(marqueur)
        if index != -1 and index < position_min:
            position_min = index
            trouve = True
    return texte[:position_min].strip() if trouve else texte


def nettoyer_markdown(texte):
    # Le fichier assistant.js affiche le texte "brut" (avec textContent),
    # donc si le modèle met quand même des ** ou des # malgré la consigne
    # qu'on lui a donnée dans le prompt, ça s'afficherait tel quel à
    # l'écran, moche. Du coup on fait un deuxième filtre ici, après coup.
    texte = re.sub(r"\*\*(.+?)\*\*", r"\1", texte)
    texte = texte.replace("**", "")
    texte = re.sub(r"^#{1,6}\s*", "", texte, flags=re.MULTILINE)
    return texte.strip()


def nettoyer_latex(texte):
    # Même souci que pour le Markdown, mais avec le LaTeX cette fois : le
    # modèle qui fait le raisonnement (deepseek) écrit parfois les formules
    # avec $$...$$ ou \(...\), une écriture spéciale faite pour être
    # interprétée par un outil comme MathJax — qu'on n'a pas installé sur la
    # page. Sans ce nettoyage, l'apprenant verrait des symboles $ et \
    # bizarres au lieu d'une vraie formule lisible.
    texte = re.sub(r"\$\$(.+?)\$\$", r"\1", texte, flags=re.DOTALL)
    texte = re.sub(r"\\\((.+?)\\\)", r"\1", texte, flags=re.DOTALL)
    texte = re.sub(r"\\\[(.+?)\\\]", r"\1", texte, flags=re.DOTALL)
    texte = texte.replace("$$", "").replace("\\(", "").replace("\\)", "")

    # Le modèle écrit parfois les commandes LaTeX SANS les délimiteurs
    # autour (juste "\frac{1}{2}" tout seul dans la phrase, sans $$ ni
    # \( \) ) — le nettoyage au-dessus ne détecte pas ce cas, donc on
    # convertit aussi les commandes les plus courantes directement, peu
    # importe qu'il y ait des délimiteurs ou non autour.
    texte = re.sub(r"\\frac\{(.+?)\}\{(.+?)\}", r"\1/\2", texte)
    texte = texte.replace("\\times", "x")
    texte = texte.replace("\\div", "/")
    texte = re.sub(r"\\sqrt\{(.+?)\}", r"racine(\1)", texte)

    return texte.strip()


def _convertir_en_chiffres(texte):
    # Le underscore devant le nom veut dire "cette fonction est pour un
    # usage interne au fichier", pas destinée à être appelée depuis
    # ailleurs (juste une convention Python, pas une vraie interdiction).
    payload = {
        "model": "nomic-embed-text:latest",
        "prompt": texte
    }
    try:
        response = requests.post(OLLAMA_EMBED_URL, json=payload, timeout=30)
        if response.status_code == 200:
            # C'est ici qu'on récupère la fameuse liste de 768 nombres.
            return response.json().get("embedding", [])
        return []
    except Exception as e:
        print(f"Erreur d'embedding : {e}", flush=True)
        return []


def prechauffer_modele():
    # Cette fonction est appelée une seule fois, au tout début, quand
    # Django démarre. Le but c'est de forcer Ollama à charger le modèle en
    # mémoire vive tout de suite, plutôt que d'attendre la première vraie
    # question de l'étudiant (qui serait alors plus lente).
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
    # PdfReader vient de la bibliothèque pypdf, elle sait lire un fichier
    # PDF et nous donner le texte de chaque page.
    from pypdf import PdfReader

    reader = PdfReader(chemin_pdf)
    texte_complet = ""
    for page in reader.pages:
        contenu = page.extract_text()
        # Certaines pages (images scannées par exemple) peuvent ne rien
        # donner du tout, donc on vérifie avant d'ajouter.
        if contenu:
            texte_complet += contenu + "\n"
    return texte_complet


def lire_et_enregistrer_pdf(doc_id, chemin_pdf, titre_cours="Document", matiere="generation_resume"):
    texte_complet = extraire_texte_pdf(chemin_pdf)

    # On découpe le texte en morceaux de 500 caractères. Cette ligne fait
    # tout le découpage d'un coup avec une "liste en compréhension" :
    # ça revient à faire une boucle qui avance de 500 en 500 dans le texte.
    taille_chunk = 500
    chunks = [texte_complet[i:i+taille_chunk] for i in range(0, len(texte_complet), taille_chunk)]

    # On prépare 4 listes vides, une pour chaque info qu'on va donner à
    # ChromaDB (le texte, son vecteur, ses infos, et son identifiant unique).
    documents = []
    embeddings = []
    metadatas = []
    ids = []

    for index, chunk in enumerate(chunks):
        vector = _convertir_en_chiffres(chunk)
        # Si jamais la vectorisation a échoué (liste vide renvoyée), on
        # n'ajoute pas ce morceau, pour ne pas polluer la base avec un
        # morceau sans vecteur associé.
        if vector:
            documents.append(chunk)
            embeddings.append(vector)
            metadatas.append({"document_id": str(doc_id), "titre": titre_cours, "matiere": matiere})
            ids.append(f"doc_{doc_id}_chunk_{index}")

    # On envoie tout à ChromaDB d'un seul coup à la fin, plutôt que morceau
    # par morceau, c'est plus rapide.
    if documents:
        collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
    return len(documents)


def generer_titre_conversation(question_utilisateur):
    # Encore une fois on demande à Qwen, mais cette fois pour trouver un
    # titre court à la conversation, un peu comme le titre d'un email.
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
            # On enlève les guillemets si jamais le modèle en a mis autour
            # du titre (ça arrive parfois, même avec la consigne donnée).
            titre = response.json().get("response", "").strip().strip('"').strip("'")
            return titre[:60] if titre else question_utilisateur[:40]
    except Exception:
        pass
    # Si tout rate, on prend juste le début de la question comme titre,
    # pour être sûr d'avoir toujours quelque chose à afficher.
    return question_utilisateur[:40]


def poser_question_a_lia(question_utilisateur, historique_messages=None, doc_id=None,
                          contexte_force=None, modele="qwen2.5:1.5b"):
    # Petit piège classique en Python : ne jamais mettre une liste vide []
    # comme valeur par défaut d'un paramètre, ça peut causer des bugs
    # bizarres. On met None et on crée la vraie liste vide ici à la place.
    if historique_messages is None:
        historique_messages = []

    question_nettoyee = question_utilisateur.strip().strip('"').strip("'")
    contexte_texte = AUCUN_CONTEXTE

    if contexte_force:
        # Cas où un PDF vient tout juste d'être déposé dans le même message.
        # On répond directement avec le début du texte extrait, sans
        # attendre que toute la vectorisation soit finie (ça prendrait trop
        # de temps pour une réponse immédiate).
        LIMITE = 2500
        extrait = contexte_force[:LIMITE]
        # On cherche le dernier point ou retour à la ligne avant la limite,
        # pour couper proprement à la fin d'une phrase plutôt qu'en plein
        # milieu d'un mot (sinon le modèle croit que le texte est cassé).
        derniere_coupure = max(extrait.rfind('. '), extrait.rfind('\n'))
        if derniere_coupure > LIMITE * 0.5:
            extrait = extrait[:derniere_coupure + 1]

        contexte_texte = (
            "Voici le début du document déposé par l'étudiant "
            "(c'est un extrait, le document peut continuer au-delà) :\n\n"
            f"{extrait}"
        )
    else:
        # === C'EST ICI QUE LE RAG COMMENCE ===
        question_vector = _convertir_en_chiffres(question_nettoyee)

        if question_vector:
            # Si un doc_id est fourni, on restreint la recherche à ce
            # document précis (question de suivi sur un PDF déjà connu).
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

                # zip() permet de parcourir deux listes en même temps, en
                # associant les éléments à la même position (le 1er doc avec
                # sa 1ère distance, etc.)
                for doc, distance in zip(docs, distances):
                    if distance <= SEUIL_PERTINENCE:
                        extraits_pertinents.append(doc)

            if extraits_pertinents:
                # On assemble tous les passages retenus, séparés par 3
                # tirets, pour que le modèle voie bien qu'il y a plusieurs
                # extraits distincts et pas un seul bloc de texte continu.
                contexte_texte = "\n---\n".join(extraits_pertinents)

    # On formate les 4 derniers messages de la conversation en texte lisible
    # pour le modèle, du genre "Étudiant: ... / Assistant LIA: ...".
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
        # Ce cas précis (aucun document trouvé) est le plus à risque
        # d'hallucination : le modèle n'a rien de concret à citer, donc il
        # pourrait répondre uniquement avec ses connaissances internes, qui
        # ne sont pas toujours fiables pour un petit modèle comme celui-ci.
        # On lui demande explicitement de dire quand il n'est pas sûr,
        # plutôt que d'affirmer une chose qui pourrait être fausse.
        if contexte_texte == AUCUN_CONTEXTE:
            instruction_contexte += (
                " Aucun cours ne correspond à cette question. Si elle porte sur un "
                "fait précis (date, capitale, chiffre, nom propre) et que tu n'es pas "
                "certain à 100% de ta réponse, dis-le clairement (par exemple : \"je "
                "ne suis pas sûr de ce fait\") au lieu d'affirmer une réponse qui "
                "pourrait être fausse."
            )

    # C'est ici que tout se rassemble : l'historique, le contexte trouvé
    # (ou pas), la consigne, et la vraie question. On dit aussi au modèle de
    # ne pas utiliser de mise en forme spéciale (Markdown ni LaTeX), et on
    # lui demande de ne jamais recommencer un tour de dialogue après sa
    # réponse (pour éviter la duplication vue en pratique).
    prompt_systeme = f"""Tu es LIA, un assistant pédagogique bienveillant et précis sur la plateforme MonEspace.
Réponds toujours en texte brut uniquement : n'utilise jamais de mise en forme Markdown (pas d'astérisques **, pas de tirets de liste, pas de titres avec #) ni de LaTeX (pas de $$, pas de \\( \\)). Écris les formules mathématiques en texte simple, par exemple : A = pi * R^2, ou "l'aire est égale à pi multiplié par le rayon au carré".
Termine ta réponse dès que tu as répondu à la question : ne recommence jamais un nouveau tour de dialogue, et ne répète jamais les libellés "Question de l'étudiant" ou "Réponse de LIA".
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
            # DeepSeek a besoin de beaucoup plus de tokens parce qu'il
            # "réfléchit" avant de répondre (le fameux bloc <think>), donc
            # sa réponse complète est plus longue que celle des autres.
            "num_predict": 700 if modele.startswith("deepseek") else 350,
            # Ça, c'est le vrai réglage qui empêche le modèle de continuer à
            # écrire après sa réponse et de repartir sur un deuxième tour :
            # dès qu'il essaie d'écrire un de ces mots, Ollama coupe tout de
            # suite la génération, avant même que ça arrive jusqu'à nous.
            "stop": [
                "\nQuestion de l'étudiant:", "\nRéponse de LIA:",
                "\nÉtudiant:", "\nAssistant LIA:",
            ],
        }
    }

    try:
        # Le timeout est monté à 180 secondes (3 minutes) parce que sur ce
        # Pi, sans carte graphique, une génération peut être lente,
        # surtout si une indexation tourne en même temps en arrière-plan.
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=180)
        if response.status_code == 200:
            texte = response.json().get("response", "Désolé, je n'ai pas pu générer de réponse.")
            # On coupe une éventuelle répétition AVANT les autres nettoyages,
            # sinon on risquerait de nettoyer du texte qui va être coupé de
            # toute façon.
            texte = tronquer_repetition(texte)
            if modele.startswith("deepseek"):
                texte = nettoyer_reponse_deepseek(texte)
            texte = nettoyer_markdown(texte)
            texte = nettoyer_latex(texte)
            return texte
        return f"Erreur du service IA (Code {response.status_code})."
    except Exception as e:
        return f"Erreur de connexion avec Ollama (Docker) : {str(e)}"
