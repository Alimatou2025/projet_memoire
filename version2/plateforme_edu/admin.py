# -*- coding: utf-8 -*-
"""
Interface d'administration Django. Permet de créer/modifier les
établissements, parcours, espaces, ressources, utilisateurs, etc.
directement depuis /admin/, sans passer par le shell.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Etablissement, Parcours, Espace, Ressource, Quiz, Video, Document,
    Utilisateur, Administrateur, Enseignant, Apprenant,
    Inscription, Evaluation, Statistiques,
    Recommandation, AssistanteIA,
)


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Plateforme", {"fields": ("role", "etablissement")}),
    )
    list_display = ("username", "first_name", "last_name", "role", "etablissement")
    list_filter = ("role", "etablissement")


@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    list_display = ("nom", "localite", "date_creation")
    search_fields = ("nom", "localite")


@admin.register(Parcours)
class ParcoursAdmin(admin.ModelAdmin):
    list_display = ("intitule", "etablissement", "date_creation")
    list_filter = ("etablissement",)
    search_fields = ("intitule",)


@admin.register(Espace)
class EspaceAdmin(admin.ModelAdmin):
    list_display = ("nom", "parcours", "date_creation")
    list_filter = ("parcours__etablissement", "parcours")
    search_fields = ("nom",)


@admin.register(Ressource)
class RessourceAdmin(admin.ModelAdmin):
    list_display = ("titre", "espace", "matiere", "enseignant", "type_ressource", "niveau_requis", "date_ajout")
    list_filter = ("type_ressource", "niveau_requis", "espace__parcours__etablissement")
    search_fields = ("titre", "matiere")


@admin.register(AssistanteIA)
class AssistanteIAAdmin(admin.ModelAdmin):
    # list_display pratique pour comparer les temps de réponse entre
    # machines (ordinateur de dev vs Raspberry Pi) pour le mémoire.
    list_display = ("question", "apprenant", "modele_utilise", "temps_reponse_secondes", "date_echange")
    list_filter = ("modele_utilise",)
    search_fields = ("question",)
    ordering = ("-date_echange",)


admin.site.register(Quiz)
admin.site.register(Video)
admin.site.register(Document)
admin.site.register(Administrateur)
admin.site.register(Enseignant)
admin.site.register(Apprenant)
admin.site.register(Inscription)
admin.site.register(Evaluation)
admin.site.register(Statistiques)
admin.site.register(Recommandation)
