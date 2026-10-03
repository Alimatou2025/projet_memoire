# -*- coding: utf-8 -*-
"""
Signaux Django : du code qui se déclenche automatiquement quand
certains événements arrivent.

Ici : dès qu'un apprenant termine un quiz (une nouvelle Evaluation
est enregistrée), on met à jour ses statistiques puis on relance le
classement K-means + la génération de recommandations pour LUI
UNIQUEMENT (pas pour tout le monde à chaque fois, pour rester rapide
sur le Raspberry Pi).

Pour activer ce fichier, ajouter dans plateforme_edu/apps.py :

    class PlateformeEduConfig(AppConfig):
        default_auto_field = "django.db.models.BigAutoField"
        name = "plateforme_edu"

        def ready(self):
            import plateforme_edu.signals  # noqa
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Evaluation, Statistiques
from .services_recommandation import classifier_apprenants, generer_recommandations


@receiver(post_save, sender=Evaluation)
def mettre_a_jour_apres_evaluation(sender, instance, created, **kwargs):
    if not created:
        return

    apprenant = instance.apprenant

    # 1. Recalcule la moyenne générale de l'apprenant
    statistiques, _ = Statistiques.objects.get_or_create(apprenant=apprenant)
    statistiques.recalculer()

    # 2. Reclasse TOUT LE MONDE avec K-means (l'algorithme a besoin
    #    de voir l'ensemble des apprenants pour former les 3 groupes).
    classifier_apprenants()

    # 3. Génère de nouvelles recommandations pour cet apprenant,
    #    avec son niveau éventuellement mis à jour.
    apprenant.refresh_from_db(fields=["niveau"])
    generer_recommandations(apprenant)
