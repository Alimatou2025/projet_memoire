import shutil

# --- 1. La vue : ne plus se fier à la session, se fier à l'URL ---

CHEMIN_VUE = "plateforme_edu/views.py"

OLD_VUE = '''def assistant_ia(request):
    """
    Page de l'assistant IA. Chaque échange (question/réponse) est
    enregistré dans AssistanteIA, rattaché à une conversation
    (conversation_id) pour permettre de retrouver et de reprendre les
    échanges passés depuis la barre latérale "Historique".
    La réponse est générée par ia_service (RAG + routage multi-modèle
    via Ollama, voir la synthèse des choix techniques du mémoire).
    """
    import uuid
    from . import ia_service
    from .models import AssistanteIA, Ressource

    profil = getattr(request.user, "profil_apprenant", None)

    if request.method == "POST" and profil is not None and request.POST.get("nouvelle_conversation"):
        request.session["conversation_id_ia"] = str(uuid.uuid4())
        return redirect("assistant_ia")

    if request.method == "POST" and profil is not None:
        question = request.POST.get("question", "").strip()
        ressource = None
        ressource_id = request.POST.get("ressource")
        if ressource_id:
            ressource = Ressource.objects.filter(id_ressource=ressource_id).first()

        document_joint = request.FILES.get("document_joint")

        if not question and document_joint:
            question = "Peux-tu m'expliquer ce document : {} ?".format(document_joint.name)

        if question:
            import time
            debut = time.perf_counter()

            conversation_id = request.session.get("conversation_id_ia")
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
                request.session["conversation_id_ia"] = conversation_id

            derniers_echanges = list(
                profil.echanges_ia.filter(conversation_id=conversation_id)
                .order_by("-date_echange")[:4]
                .values_list("question", "reponse")
            )
            derniers_echanges.reverse()

            passages = []
            try:
                if document_joint is not None:
                    passages = ia_service.rechercher_passages_fichier_televerse(question, document_joint)
                elif ressource is not None and hasattr(ressource, "document") and ressource.document.indexe:
                    passages = ia_service.rechercher_passages_document(question, ressource.document)

                reponse, modele_utilise = ia_service.generer_reponse(question, passages, derniers_echanges)
            except ia_service.ErreurServiceIA:
                reponse = (
                    "Désolé, je n'ai pas pu contacter le service IA local (Ollama). "
                    "Vérifie que le conteneur `memoire_ia` tourne bien, puis réessaie."
                )
                modele_utilise = ""

            temps_reponse = round(time.perf_counter() - debut, 2)

            AssistanteIA.objects.create(
                apprenant=profil,
                ressource=ressource,
                document_joint=document_joint,
                question=question,
                reponse=reponse,
                modele_utilise=modele_utilise,
                temps_reponse_secondes=temps_reponse,
                conversation_id=conversation_id,
            )
        return redirect("assistant_ia")

    contexte = {}
    if profil is not None:
        echanges_groupes = {}
        for echange in profil.echanges_ia.exclude(conversation_id__isnull=True).order_by("date_echange"):
            groupe = echanges_groupes.setdefault(echange.conversation_id, {
                "conversation_id": echange.conversation_id,
                "premiere_question": echange.question,
                "derniere_date": echange.date_echange,
                "nombre_echanges": 0,
            })
            groupe["nombre_echanges"] += 1
            groupe["derniere_date"] = echange.date_echange

        contexte["historique_recent"] = sorted(
            echanges_groupes.values(), key=lambda g: g["derniere_date"], reverse=True
        )

        conversation_affichee = request.GET.get("conversation") or request.session.get("conversation_id_ia")
        contexte["historique"] = (
            profil.echanges_ia.filter(conversation_id=conversation_affichee).order_by("date_echange")
            if conversation_affichee else profil.echanges_ia.none()
        )

        contexte["ressources_disponibles"] = Ressource.objects.filter(
            espace__parcours__inscriptions__apprenant=profil
        ).distinct()

    return render(request, "assistant_ia.html", contexte)'''

NEW_VUE = '''def assistant_ia(request):
    """
    Page de l'assistant IA. À l'ouverture de la page (sans conversation
    précisée dans l'URL), on affiche un écran d'accueil vide — comme sur
    Claude ou ChatGPT — pas automatiquement la dernière conversation.
    Une conversation ne s'affiche que si son identifiant est explicitement
    dans l'URL (?conversation=<uuid>) : soit parce que l'apprenant clique
    dessus dans la barre latérale "Historique", soit parce qu'il vient
    d'envoyer un message (la page se redirige alors vers cette URL précise
    pour qu'il voie la réponse).
    """
    import uuid
    from django.urls import reverse
    from . import ia_service
    from .models import AssistanteIA, Ressource

    profil = getattr(request.user, "profil_apprenant", None)

    if request.method == "POST" and profil is not None and request.POST.get("nouvelle_conversation"):
        return redirect("assistant_ia")

    if request.method == "POST" and profil is not None:
        question = request.POST.get("question", "").strip()
        ressource = None
        ressource_id = request.POST.get("ressource")
        if ressource_id:
            ressource = Ressource.objects.filter(id_ressource=ressource_id).first()

        document_joint = request.FILES.get("document_joint")

        if not question and document_joint:
            question = "Peux-tu m'expliquer ce document : {} ?".format(document_joint.name)

        # Identifiant de la conversation en cours, transmis par le champ
        # caché du formulaire (vide si on vient de l'écran d'accueil).
        conversation_id = request.POST.get("conversation_id") or ""

        if question:
            import time
            debut = time.perf_counter()

            if not conversation_id:
                conversation_id = str(uuid.uuid4())

            derniers_echanges = list(
                profil.echanges_ia.filter(conversation_id=conversation_id)
                .order_by("-date_echange")[:4]
                .values_list("question", "reponse")
            )
            derniers_echanges.reverse()

            passages = []
            try:
                if document_joint is not None:
                    passages = ia_service.rechercher_passages_fichier_televerse(question, document_joint)
                elif ressource is not None and hasattr(ressource, "document") and ressource.document.indexe:
                    passages = ia_service.rechercher_passages_document(question, ressource.document)

                reponse, modele_utilise = ia_service.generer_reponse(question, passages, derniers_echanges)
            except ia_service.ErreurServiceIA:
                reponse = (
                    "Désolé, je n'ai pas pu contacter le service IA local (Ollama). "
                    "Vérifie que le conteneur `memoire_ia` tourne bien, puis réessaie."
                )
                modele_utilise = ""

            temps_reponse = round(time.perf_counter() - debut, 2)

            AssistanteIA.objects.create(
                apprenant=profil,
                ressource=ressource,
                document_joint=document_joint,
                question=question,
                reponse=reponse,
                modele_utilise=modele_utilise,
                temps_reponse_secondes=temps_reponse,
                conversation_id=conversation_id,
            )
            return redirect(reverse("assistant_ia") + "?conversation=" + conversation_id)

        return redirect("assistant_ia")

    contexte = {}
    if profil is not None:
        echanges_groupes = {}
        for echange in profil.echanges_ia.exclude(conversation_id__isnull=True).order_by("date_echange"):
            groupe = echanges_groupes.setdefault(echange.conversation_id, {
                "conversation_id": echange.conversation_id,
                "premiere_question": echange.question,
                "derniere_date": echange.date_echange,
                "nombre_echanges": 0,
            })
            groupe["nombre_echanges"] += 1
            groupe["derniere_date"] = echange.date_echange

        contexte["historique_recent"] = sorted(
            echanges_groupes.values(), key=lambda g: g["derniere_date"], reverse=True
        )

        # Écran d'accueil vide par défaut : seule une conversation demandée
        # explicitement dans l'URL est affichée.
        conversation_affichee = request.GET.get("conversation") or ""
        contexte["conversation_active"] = conversation_affichee
        contexte["historique"] = (
            profil.echanges_ia.filter(conversation_id=conversation_affichee).order_by("date_echange")
            if conversation_affichee else profil.echanges_ia.none()
        )

        contexte["ressources_disponibles"] = Ressource.objects.filter(
            espace__parcours__inscriptions__apprenant=profil
        ).distinct()

    return render(request, "assistant_ia.html", contexte)'''

# --- 2. Le template : champ caché pour transmettre la conversation active ---

CHEMIN_TEMPLATE = "templates/assistant_ia.html"

OLD_TEMPLATE = '''            <form method="post" enctype="multipart/form-data" class="zone-saisie-chat">
                {% csrf_token %}

                {% if ressources_disponibles %}'''

NEW_TEMPLATE = '''            <form method="post" enctype="multipart/form-data" class="zone-saisie-chat">
                {% csrf_token %}
                <input type="hidden" name="conversation_id" value="{{ conversation_active }}">

                {% if ressources_disponibles %}'''

def patcher(chemin, old, new, etiquette):
    with open(chemin, "r", encoding="utf-8") as f:
        contenu = f.read()
    if old not in contenu:
        print(f"ERREUR ({etiquette}) : le texte attendu n'a pas été trouvé. Rien modifié dans {chemin}.")
        return False
    shutil.copy(chemin, chemin + ".bak2")
    contenu = contenu.replace(old, new, 1)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)
    print(f"OK ({etiquette}) : {chemin} modifié. Sauvegarde : {chemin}.bak2")
    return True

ok1 = patcher(CHEMIN_VUE, OLD_VUE, NEW_VUE, "vue")
ok2 = patcher(CHEMIN_TEMPLATE, OLD_TEMPLATE, NEW_TEMPLATE, "template")

if ok1 and ok2:
    print("Tout est bon, tu peux redémarrer le conteneur.")
