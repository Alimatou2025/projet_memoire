import shutil

CHEMIN = "plateforme_edu/views.py"

OLD = '''def assistant_ia(request):
    """
    Page de l'assistant IA. Chaque échange (question/réponse) est
    enregistré dans AssistanteIA pour garder l'historique visible et
    éviter que le message tapé ne disparaisse après l'envoi.
    La réponse est générée par ia_service (RAG + routage multi-modèle
    via Ollama, voir la synthèse des choix techniques du mémoire).
    """
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime
    from . import ia_service
    from .models import AssistanteIA, Ressource

    profil = getattr(request.user, "profil_apprenant", None)

    if request.method == "POST" and profil is not None and request.POST.get("nouvelle_conversation"):
        request.session["debut_conversation_ia"] = timezone.now().isoformat()
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

            derniers_echanges = list(
                profil.echanges_ia.order_by("-date_echange")[:4].values_list("question", "reponse")
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
            )
        return redirect("assistant_ia")

    contexte = {}
    if profil is not None:
        tous_les_echanges = profil.echanges_ia.order_by("date_echange")
        contexte["historique_recent"] = profil.echanges_ia.order_by("-date_echange")

        if request.GET.get("revenir"):
            contexte["historique"] = tous_les_echanges
        else:
            debut_iso = request.session.get("debut_conversation_ia")
            debut = parse_datetime(debut_iso) if debut_iso else None
            contexte["historique"] = (
                tous_les_echanges.filter(date_echange__gte=debut) if debut else tous_les_echanges
            )

        contexte["ressources_disponibles"] = Ressource.objects.filter(
            espace__parcours__inscriptions__apprenant=profil
        ).distinct()

    return render(request, "assistant_ia.html", contexte)'''

NEW = '''def assistant_ia(request):
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

with open(CHEMIN, "r", encoding="utf-8") as f:
    contenu = f.read()

if OLD not in contenu:
    print("ERREUR : l'ancien code n'a pas été trouvé tel quel dans le fichier.")
    print("Rien n'a été modifié. Dis-le à Claude pour ajuster le script.")
else:
    shutil.copy(CHEMIN, CHEMIN + ".bak")
    nouveau_contenu = contenu.replace(OLD, NEW, 1)
    with open(CHEMIN, "w", encoding="utf-8") as f:
        f.write(nouveau_contenu)
    print("OK : fonction assistant_ia remplacée avec succès.")
    print("Une sauvegarde de l'ancien fichier a été créée : " + CHEMIN + ".bak")
