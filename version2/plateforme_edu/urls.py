from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.accueil, name="accueil"),
    path("connexion/", views.connexion, name="connexion"),
    path("inscription/", views.inscription, name="inscription"),
    path("deconnexion/", views.deconnexion, name="deconnexion"),
    path("mon-compte/", views.changer_mot_de_passe, name="changer_mot_de_passe"),

    path("admin-tableau-bord/", views.tableau_bord_admin, name="tableau_bord_admin"),
    path("admin-etablissement/", views.gerer_etablissement, name="gerer_etablissement"),
    path("admin-etablissement/supprimer/", views.supprimer_etablissement, name="supprimer_etablissement"),
    path("admin-utilisateurs/", views.gerer_utilisateurs, name="gerer_utilisateurs"),
    path("admin-parcours/", views.gerer_parcours, name="gerer_parcours"),
    path("enseignant-tableau-bord/", views.tableau_bord_enseignant, name="tableau_bord_enseignant"),
    path("apprenant-tableau-bord/", views.tableau_bord_apprenant, name="tableau_bord_apprenant"),

    path("mes-ressources/", views.mes_ressources, name="mes_ressources"),
    path("mes-ressources/<uuid:id_ressource>/modifier/", views.modifier_ressource, name="modifier_ressource"),
    path("mes-ressources/<uuid:id_ressource>/supprimer/", views.supprimer_ressource, name="supprimer_ressource"),
    path("assistant-ia/", views.assistant_ia, name="assistant_ia"),

    path("parcours/", views.parcours_disponibles, name="parcours_disponibles"),
    path("quiz/<uuid:id_ressource>/passer/", views.passer_quiz, name="passer_quiz"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
