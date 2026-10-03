import os, django, time
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plateforme_edu.settings")
django.setup()

from plateforme_edu.models import Document
from plateforme_edu.ia_service import indexer_document

FICHIER_PROGRES = "reindex_fait.txt"

try:
    with open(FICHIER_PROGRES) as f:
        deja_fait = set(f.read().split())
except FileNotFoundError:
    deja_fait = set()

ids = list(Document.objects.filter(indexe=True).values_list("pk", flat=True))
restants = [pk for pk in ids if str(pk) not in deja_fait]
total = len(ids)
print(f"{total} documents au total, {len(restants)} restants", flush=True)

for i, pk in enumerate(restants, 1):
    doc = Document.objects.get(pk=pk)
    titre = doc.ressource.titre if doc.ressource else pk
    try:
        indexer_document(doc)
        with open(FICHIER_PROGRES, "a") as f:
            f.write(f"{pk}\n")
        print(f"{i}/{len(restants)} OK : {titre}", flush=True)
    except Exception as e:
        print(f"{i}/{len(restants)} ECHEC : {titre} -> {e}", flush=True)
    time.sleep(3)

print("Termine.", flush=True)
