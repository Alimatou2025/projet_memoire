import os
import threading
from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from . import views
from .ia_service import prechauffer_modele
def home(request):
    return render(request, 'index.html')
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('assistant_ia/', views.assistant_ia, name='assistant_ia'),
    path('ressource/ajouter/', views.ajouter_ressource, name='ajouter_ressource'),
    path('conversations/', views.lister_conversations, name='lister_conversations'),
    path('conversations/<int:conversation_id>/', views.charger_conversation, name='charger_conversation'),
    path('conversations/<int:conversation_id>/renommer/', views.renommer_conversation, name='renommer_conversation'),
    path('recommandation/', views.recommandation, name='recommandation'),
    path('<path:unused>', home, name='catchall'),
]
if os.environ.get('RUN_MAIN') == 'true':
    threading.Thread(target=prechauffer_modele, daemon=True).start()
