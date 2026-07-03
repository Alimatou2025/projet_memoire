import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

OLLAMA_API = "http://ollama:11434/api/generate"

@csrf_exempt
def assistant_ia(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_question = data.get('question', '')

            system_prompt = (
                "Tu es un assistant pédagogique expert en informatique, réseaux et DevOps. "
                "Réponds de manière claire, structurée, en français et adapte à un étudiant."
            )

            payload = {
                "model": "gemma2:2b",
              "prompt": f"{system_prompt}\ninstruction: {user_question}",
                "stream": False
            }

            response = requests.post(OLLAMA_API, json=payload, timeout=60)
            res_data = response.json()

            return JsonResponse({
                "status": "success",
                "reponse": res_data.get('response', '')
            })
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)