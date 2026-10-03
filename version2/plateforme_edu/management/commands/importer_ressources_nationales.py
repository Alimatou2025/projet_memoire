# -*- coding: utf-8 -*-
"""
Commande d'import des ressources nationales par défaut (bibliothèque
numérique du MEN Sénégal, plateforme SENKALA) — le contenu accessible à
tout apprenant même sans établissement rattaché (voir section 3.8 /
limites du mémoire, et la migration 0006 qui rend Ressource.espace
optionnel pour ce cas précis).

Utilisation (depuis le conteneur web, ou en local si Ollama est
joignable) :

    python manage.py importer_ressources_nationales

Chaque fichier .md du dossier ressources_nationales/senkala/ est lu,
son en-tête YAML (titre / matiere / niveau / source) est extrait, une
Ressource + un Document sont créés avec espace=None (contenu national),
puis le document est indexé (segments + embeddings) via ia_service,
exactement comme un document déposé par un enseignant.

La commande est idempotente : un document déjà importé (même titre,
espace nul) n'est pas recréé, seulement ré-indexé si besoin.
"""

import os
import re

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from ... import ia_service
from ...models import Ressource, Document


DOSSIER_PAR_DEFAUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "ressources_nationales", "senkala",
)


def _parser_entete_yaml(texte):
    """Extrait les champs `cle: valeur` du bloc YAML --- ... --- en tête
    du fichier, sans dépendance externe (pas besoin de PyYAML pour un
    format aussi simple, à plat, sans imbrication)."""
    entete = {}
    corps = texte
    if texte.startswith("---"):
        fin = texte.find("---", 3)
        if fin != -1:
            bloc = texte[3:fin].strip()
            corps = texte[fin + 3:].lstrip("\n")
            for ligne in bloc.splitlines():
                if ":" in ligne:
                    cle, valeur = ligne.split(":", 1)
                    entete[cle.strip()] = valeur.strip()
    return entete, corps


class Command(BaseCommand):
    help = "Importe et indexe les documents SENKALA comme ressources nationales par défaut."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dossier",
            default=os.path.normpath(DOSSIER_PAR_DEFAUT),
            help="Dossier contenant les fichiers .md à importer (par défaut : ressources_nationales/senkala/).",
        )
        parser.add_argument(
            "--sans-index",
            action="store_true",
            help="Crée les ressources sans lancer l'indexation RAG (utile si Ollama n'est pas joignable maintenant).",
        )

    def handle(self, *args, **options):
        dossier = options["dossier"]
        sans_index = options["sans_index"]

        if not os.path.isdir(dossier):
            self.stderr.write(self.style.ERROR(f"Dossier introuvable : {dossier}"))
            return

        fichiers = sorted(f for f in os.listdir(dossier) if f.endswith(".md"))
        if not fichiers:
            self.stderr.write(self.style.WARNING(f"Aucun fichier .md trouvé dans {dossier}"))
            return

        for nom_fichier in fichiers:
            chemin = os.path.join(dossier, nom_fichier)
            with open(chemin, "r", encoding="utf-8") as f:
                texte_brut = f.read()

            entete, corps = _parser_entete_yaml(texte_brut)
            titre = entete.get("titre") or nom_fichier
            matiere = entete.get("matiere", "")
            source = entete.get("source", "")

            ressource_existante = Ressource.objects.filter(
                titre=titre, espace__isnull=True
            ).first()

            if ressource_existante is not None:
                ressource = ressource_existante
                self.stdout.write(f"Déjà présente, on ne recrée pas : {titre}")
            else:
                ressource = Ressource.objects.create(
                    espace=None,
                    enseignant=None,
                    titre=titre,
                    type_ressource=Ressource.TYPE_DOCUMENT,
                    matiere=matiere,
                    source_externe=source,
                )
                document = Document.objects.create(ressource=ressource)
                # Le corps (markdown, sans l'en-tête) tient lieu de "PDF" :
                # ia_service.indexer_document lit n'importe quel texte, pas
                # seulement un PDF (voir extraire_texte_pdf vs. lecture
                # brute selon l'extension du fichier).
                nom_stocke = re.sub(r"[^a-zA-Z0-9_.-]", "_", nom_fichier)
                document.fichier.save(nom_stocke, ContentFile(corps.encode("utf-8")), save=True)
                self.stdout.write(self.style.SUCCESS(f"Créée : {titre} ({matiere})"))

            document = ressource.document
            if not sans_index:
                try:
                    ia_service.indexer_document(document)
                    self.stdout.write(f"  → indexée ({document.segments.count()} segments)")
                except ia_service.ErreurServiceIA as erreur:
                    self.stderr.write(self.style.WARNING(f"  → indexation impossible pour l'instant : {erreur}"))

        self.stdout.write(self.style.SUCCESS("Import terminé."))
