# -*- coding: utf-8 -*-
"""
Commande de gestion Django.

Lancer avec :
    python3 manage.py generer_recommandations

À exécuter après que des apprenants ont passé de nouveaux quiz, pour
mettre à jour leur niveau (K-means) et générer leurs recommandations.
"""

from django.core.management.base import BaseCommand

from plateforme_edu.services_recommandation import rafraichir_toutes_les_recommandations


class Command(BaseCommand):
    help = "Reclasse les apprenants par niveau (K-means) et génère leurs recommandations."

    def handle(self, *args, **options):
        resultat = rafraichir_toutes_les_recommandations()

        self.stdout.write(self.style.SUCCESS(
            f"{resultat['apprenants_reclasses']} apprenant(s) reclassé(s), "
            f"{resultat['recommandations_creees']} nouvelle(s) recommandation(s) créée(s)."
        ))
