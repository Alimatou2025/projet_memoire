import hashlib
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from plateforme_edu.ia_service import collection


class Command(BaseCommand):
    help = (
        "Détecte les PDF dupliqués (même contenu, uploadés plusieurs fois pendant "
        "les tests) dans media/cours, et supprime les copies en trop ainsi que "
        "leurs chunks correspondants dans ChromaDB."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche ce qui serait supprimé, sans rien supprimer réellement.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        media_dir = os.path.join(settings.BASE_DIR, "media", "cours")

        if not os.path.isdir(media_dir):
            self.stdout.write(self.style.WARNING(f"Dossier introuvable : {media_dir}"))
            return

        fichiers = [f for f in os.listdir(media_dir) if f.lower().endswith(".pdf")]
        groupes = {}  # empreinte -> liste de (nom_fichier, doc_id, date_modification)

        for nom_fichier in fichiers:
            chemin = os.path.join(media_dir, nom_fichier)
            with open(chemin, "rb") as f:
                contenu = f.read()
            empreinte = hashlib.sha256(contenu).hexdigest()
            doc_id = os.path.splitext(nom_fichier)[0]
            mtime = os.path.getmtime(chemin)
            groupes.setdefault(empreinte, []).append((nom_fichier, doc_id, mtime))

        total_doublons = 0

        for empreinte, entrees in groupes.items():
            if len(entrees) <= 1:
                continue

            # On garde la copie la plus ANCIENNE (première fois indexée),
            # on supprime les copies plus récentes issues des tests répétés.
            entrees.sort(key=lambda e: e[2])
            a_garder, *a_supprimer = entrees

            self.stdout.write(
                f"\n📄 Doublon détecté ({len(entrees)} copies, empreinte {empreinte[:10]}...)"
            )
            self.stdout.write(f"   ✅ Conservé : {a_garder[0]}")

            for nom_fichier, doc_id, _ in a_supprimer:
                total_doublons += 1
                self.stdout.write(f"   ❌ Supprimé : {nom_fichier}")

                if not dry_run:
                    chemin = os.path.join(media_dir, nom_fichier)
                    if os.path.exists(chemin):
                        os.remove(chemin)

                    try:
                        collection.delete(where={"document_id": doc_id})
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f"      ⚠️ Erreur ChromaDB pour {doc_id} : {e}")
                        )

        if total_doublons == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ Aucun doublon trouvé."))
        elif dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n🔍 Mode simulation : {total_doublons} doublon(s) seraient "
                    f"supprimés. Relance sans --dry-run pour appliquer."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n✅ {total_doublons} doublon(s) supprimé(s).")
            )
