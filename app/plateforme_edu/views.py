import os
import json
import uuid
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from .ia_service import poser_question_a_lia, lire_et_enregistrer_pdf

HISTORIQUE_SESSIONS = {}


@csrf_exempt
def assistant_ia(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            question = data.get("question", "").strip()
            doc_id = data.get("doc_id", None)
        except json.JSONDecodeError:
            question = request.POST.get("question", "").strip()
            doc_id = request.POST.get("doc_id", None)

        if not question:
            return JsonResponse({"erreur": "La question est vide"}, status=400)

        if not request.session.session_key:
            request.session.save()
        session_id = request.session.session_key

        historique = HISTORIQUE_SESSIONS.get(session_id, [])

        print(f"\n🔍 DEBUG - Session: {session_id} | Nb msgs dans historique: {len(historique)}", flush=True)

        reponse = poser_question_a_lia(
            question_utilisateur=question,
            historique_messages=historique,
            doc_id=doc_id,
            modele="qwen2.5:1.5b"
        )

        historique.append({"role": "user", "content": question})
        historique.append({"role": "assistant", "content": reponse})
        HISTORIQUE_SESSIONS[session_id] = historique[-6:]

        return JsonResponse({"reponse": reponse, "status": "success"})

    return render(request, "index.html")


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
