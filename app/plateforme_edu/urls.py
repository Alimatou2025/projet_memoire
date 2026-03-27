from django.contrib import admin
from django.urls import path
from django.shortcuts import render

# Cette petite fonction dit à Django d'afficher ton index.html
def home(request):
    return render(request, 'index.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'), # Le chemin vide '' signifie la page d'accueil
]
