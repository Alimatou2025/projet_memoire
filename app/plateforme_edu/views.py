from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .ia_service import lire_et_enregistrer_pdf, poser_question_a_lia

def home(request):
    return render(request, 'index.html')

@csrf_exempt
def assistant_ia(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            question = data.get('question', '')
            
            # Appel à ton ia_service
            reponse = poser_question_a_lia(question)
            
            return JsonResponse({'reponse': reponse})
        except Exception as e:
            # On passe le statut à 200 pour que le JavaScript gère proprement l'affichage du texte d'erreur
            return JsonResponse({'reponse': f"Erreur de communication avec l'IA dans Docker : {str(e)}"}, status=200)
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

@csrf_exempt
def ajouter_ressource(request):
    if request.method == 'POST' and request.FILES.get('fichier'):
        try:
            titre = request.POST.get('titre', 'Sans titre')
            fichier = request.FILES['fichier']
            
            # CORRECTION ICI : On ne récupère qu'une seule variable (le booléen)
            # Inverse fichier et titre pour correspondre à la définition de la fonction
            success = lire_et_enregistrer_pdf(titre, fichier)
            
            if success:
                return JsonResponse({'status': 'success', 'titre': titre, 'ia': 'Indexé dans ChromaDB ✅'})
            else:
                return JsonResponse({'status': 'error', 'message': "L'indexation dans ChromaDB a échoué."})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Requête invalide'})