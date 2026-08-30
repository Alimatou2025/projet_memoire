import os
import json
import uuid
import threading
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from .ia_service import (
    poser_question_a_lia,
    lire_et_enregistrer_pdf,
    extraire_texte_pdf,
    generer_titre_conversation,
    modele_pour_matiere,
    classifier_matiere,
)
from .models import Conversation, Message, Document

def _get_session_id(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key

@csrf_exempt
def assistant_ia(request):
    if request.method == "POST":
        # On accepte maintenant un multipart/form-data : question + fichier (optionnel)
        # peuvent arriver dans la MÊME requête, comme sur Claude/Gemini.
        question = request.POST.get("question", "").strip()
        conversation_id = request.POST.get("conversation_id") or None
        fichier = request.FILES.get("fichier")

        doc_id = request.POST.get("doc_id") or None
        titre_doc = None
        contexte_immediat = None
        matiere = None  # décidée automatiquement par le "chef" ci-dessous

        if fichier:
            titre_doc = request.POST.get("titre", "").strip() or fichier.name
            doc_id = str(uuid.uuid4())

            media_dir = os.path.join(settings.BASE_DIR, "media", "cours")
            os.makedirs(media_dir, exist_ok=True)
            extension = os.path.splitext(fichier.name)[1]
            chemin_pdf = os.path.join(media_dir, f"{doc_id}{extension}")

            with open(chemin_pdf, "wb+") as destination:
                for chunk in fichier.chunks():
                    destination.write(chunk)

            # Extraction texte immédiate (rapide, pas d'appel Ollama) pour
            # pouvoir répondre à la question tout de suite.
            contexte_immediat = extraire_texte_pdf(chemin_pdf)

            # Le "chef" (qwen2.5:1.5b) classe automatiquement la matière du
            # document : sur la question si elle existe, sinon sur le début
            # du texte extrait du PDF.
            texte_a_classer = question if question else contexte_immediat[:300]
            matiere = classifier_matiere(texte_a_classer)

            Document.objects.create(doc_id=doc_id, titre=titre_doc, matiere=matiere)
        elif doc_id:
            # Question de suivi sur un document déjà connu : on retrouve sa matière
            # pour continuer à utiliser le bon modèle.
            doc = Document.objects.filter(doc_id=doc_id).first()
            if doc:
                matiere = doc.matiere

        if not question and not fichier:
            return JsonResponse({"erreur": "La question est vide"}, status=400)

        session_id = _get_session_id(request)

        if conversation_id:
            conversation = Conversation.objects.filter(id=conversation_id, session_id=session_id).first()
        else:
            conversation = None

        if not conversation:
            # Si un document est attaché, on donne au générateur de titre son nom
            # + la question (même vague) : sans ça, une question générique comme
            # "explique moi ceci" produit un titre générique ("Explication demandée")
            # au lieu d'un vrai sujet identifiable.
            if titre_doc:
                base_titre = f"Document \"{titre_doc}\" : {question}" if question else f"Document : {titre_doc}"
            else:
                base_titre = question
            titre_auto = generer_titre_conversation(base_titre)
            conversation = Conversation.objects.create(session_id=session_id, titre=titre_auto)

        reponse = None
        if question:
            messages_precedents = list(conversation.messages.all().order_by('-date')[:6])[::-1]
            historique = [{"role": m.role, "content": m.contenu} for m in messages_precedents]

            # Pas de document associé (conversation générale) : le "chef" classe
            # automatiquement la matière à partir de la question elle-même.
            matiere_effective = matiere or classifier_matiere(question)

            reponse = poser_question_a_lia(
                question_utilisateur=question,
                historique_messages=historique,
                doc_id=doc_id,
                contexte_force=contexte_immediat,
                modele=modele_pour_matiere(matiere_effective)
            )

            Message.objects.create(conversation=conversation, role="user", contenu=question)
            Message.objects.create(conversation=conversation, role="assistant", contenu=reponse)

        # L'indexation vectorielle complète (embeddings) démarre APRÈS la réponse,
        # pour ne pas se disputer le CPU du Pi avec la génération en cours.
        # Elle prépare le RAG pour les PROCHAINES questions sur ce document.
        if fichier:
            threading.Thread(
                target=lire_et_enregistrer_pdf,
                kwargs={
                    "doc_id": doc_id,
                    "chemin_pdf": chemin_pdf,
                    "titre_cours": titre_doc,
                    "matiere": matiere,
                },
                daemon=True,
            ).start()

        return JsonResponse({
            "reponse": reponse,
            "status": "success",
            "conversation_id": conversation.id,
            "titre": conversation.titre,
            "doc_id": doc_id,
            "doc_titre": titre_doc,
        })

    return render(request, "index.html")

def lister_conversations(request):
    session_id = _get_session_id(request)
    conversations = Conversation.objects.filter(session_id=session_id).order_by('-date_creation')
    data = [
        {"id": c.id, "titre": c.titre, "date_creation": c.date_creation.isoformat()}
        for c in conversations
    ]
    return JsonResponse({"conversations": data})

def charger_conversation(request, conversation_id):
    session_id = _get_session_id(request)
    conversation = Conversation.objects.filter(id=conversation_id, session_id=session_id).first()
    if not conversation:
        return JsonResponse({"erreur": "Conversation introuvable"}, status=404)
    messages = conversation.messages.all().order_by('date')
    data = [{"role": m.role, "contenu": m.contenu} for m in messages]
    return JsonResponse({"conversation_id": conversation.id, "titre": conversation.titre, "messages": data})

@csrf_exempt
def renommer_conversation(request, conversation_id):
    if request.method == "POST":
        session_id = _get_session_id(request)
        conversation = Conversation.objects.filter(id=conversation_id, session_id=session_id).first()
        if not conversation:
            return JsonResponse({"erreur": "Conversation introuvable"}, status=404)
        try:
            data = json.loads(request.body)
            nouveau_titre = data.get("titre", "").strip()
        except json.JSONDecodeError:
            nouveau_titre = ""
        if not nouveau_titre:
            return JsonResponse({"erreur": "Titre vide"}, status=400)
        conversation.titre = nouveau_titre[:100]
        conversation.save()
        return JsonResponse({"status": "success", "titre": conversation.titre})
    return JsonResponse({"erreur": "Méthode non autorisée"}, status=405)

@csrf_exempt
def ajouter_ressource(request):
    if request.method == "POST" and request.FILES.get("fichier"):
        fichier = request.FILES["fichier"]
        titre = request.POST.get("titre", "").strip() or fichier.name
        matiere = request.POST.get("matiere") or "generation_resume"
        doc_id = str(uuid.uuid4())
        media_dir = os.path.join(settings.BASE_DIR, "media", "cours")
        os.makedirs(media_dir, exist_ok=True)
        extension = os.path.splitext(fichier.name)[1]
        nom_fichier_unique = f"{doc_id}{extension}"
        chemin_pdf = os.path.join(media_dir, nom_fichier_unique)
        with open(chemin_pdf, "wb+") as destination:
            for chunk in fichier.chunks():
                destination.write(chunk)
        Document.objects.create(doc_id=doc_id, titre=titre, matiere=matiere)
        nb_chunks = lire_et_enregistrer_pdf(
            doc_id=doc_id,
            chemin_pdf=chemin_pdf,
            titre_cours=titre,
            matiere=matiere,
        )
        return JsonResponse({
            "status": "success",
            "titre": titre,
            "ia": f"({nb_chunks} blocs indexés dans la base de connaissances)",
            "doc_id": doc_id
        })
    return JsonResponse({"erreur": "Aucun fichier fourni ou méthode non autorisée"}, status=400)

def recommandation(request):
    """Affiche les profils générés par le clustering K-means, répartis en
    3 catégories (débutant/moyen/excellent), avec une recommandation
    pédagogique par catégorie."""
    from .models import Recommandation
    recommandations = Recommandation.objects.exclude(profilApp__isnull=True)

    groupes = {"debutant": [], "moyen": [], "excellent": []}
    for r in recommandations:
        if r.profilApp in groupes:
            groupes[r.profilApp].append(r)

    contexte = {
        "groupes": groupes,
        "recommandations_texte": {
            nom: Recommandation.recommandation_pour_profil(nom)
            for nom in groupes
        },
        "total": recommandations.count(),
        "source": "OULAD (validation externe, données réelles)",
    }
    return render(request, "recommandation.html", contexte)
