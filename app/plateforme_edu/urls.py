from . import views
from django.contrib import admin
from django.urls import path
from django.shortcuts import render

# Cette fonction affiche la page d'accueil index.html
def home(request):
    return render(request, 'index.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('assistant_ia/', views.assistant_ia, name='assistant_ia'),
    path('ressource/ajouter/', views.ajouter_ressource, name='ajouter_ressource'),
]
# --- PRÉCHAUFFAGE DU MODÈLE EN ARRIÈRE-PLAN ---
import os
import threading
from .ia_service import prechauffer_modele

if os.environ.get('RUN_MAIN') == 'true':
    threading.Thread(target=prechauffer_modele, daemon=True).start()