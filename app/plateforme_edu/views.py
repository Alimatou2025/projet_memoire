import os
import json
import uuid
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from .ia_service import poser_question_a_lia, lire_et_enregistrer_pdf, generer_titre_conversation
from .models import Conversation, Message

def _get_session_id(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key

@csrf_exempt
def assistant_ia(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            question = data.get("question", "").strip()
            doc_id = data.get("doc_id", None)
            conversation_id = data.get("conversation_id", None)
        except json.JSONDecodeError:
            question = request.POST.get("question", "").strip()
            doc_id = request.POST.get("doc_id", None)
            conversation_id = request.POST.get("conversation_id", None)

        if not question:
            return JsonResponse({"erreur": "La question est vide"}, status=400)

        session_id = _get_session_id(request)

        if conversation_id:
            conversation = Conversation.objects.filter(id=conversation_id, session_id=session_id).first()
        else:
            conversation = None

        if not conversation:
            titre_auto = generer_titre_conversation(question)
            conversation = Conversation.objects.create(session_id=session_id, titre=titre_auto)

        messages_precedents = list(conversation.messages.all().order_by('-date')[:6])[::-1]
        historique = [{"role": m.role, "content": m.contenu} for m in messages_precedents]

        reponse = poser_question_a_lia(
            question_utilisateur=question,
            historique_messages=historique,
            doc_id=doc_id,
            modele="qwen2.5:1.5b"
        )

        Message.objects.create(conversation=conversation, role="user", contenu=question)
        Message.objects.create(conversation=conversation, role="assistant", contenu=reponse)

        return JsonResponse({
            "reponse": reponse,
            "status": "success",
            "conversation_id": conversation.id,
            "titre": conversation.titre
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
        doc_id = str(uuid.uuid4())
        media_dir = os.path.join(settings.BASE_DIR, "media", "cours")
        os.makedirs(media_dir, exist_ok=True)
        extension = os.path.splitext(fichier.name)[1]
        nom_fichier_unique = f"{doc_id}{extension}"
        chemin_pdf = os.path.join(media_dir, nom_fichier_unique)
        with open(chemin_pdf, "wb+") as destination:
            for chunk in fichier.chunks():
                destination.write(chunk)
        nb_chunks = lire_et_enregistrer_pdf(
            doc_id=doc_id,
            chemin_pdf=chemin_pdf,
            titre_cours=titre
        )
        return JsonResponse({
            "status": "success",
            "titre": titre,
            "ia": f"({nb_chunks} blocs indexés dans la base de connaissances)",
            "doc_id": doc_id
        })
    return JsonResponse({"erreur": "Aucun fichier fourni ou méthode non autorisée"}, status=400)
