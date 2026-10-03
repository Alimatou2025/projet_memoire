#!/bin/bash
touch reindex_fait.txt
pk=$(comm -23 <(sort ids_tous.txt) <(sort reindex_fait.txt) | head -n 1)

if [ -z "$pk" ]; then
    echo "Tout est deja fait !"
    exit 0
fi

echo "Traitement de : $pk"
python manage.py shell -c "
from plateforme_edu.models import Document
from plateforme_edu.ia_service import indexer_document
doc = Document.objects.get(pk='$pk')
indexer_document(doc)
print('OK :', doc.ressource.titre)
"

if [ $? -eq 0 ]; then
    echo "$pk" >> reindex_fait.txt
    echo "Enregistre comme fait."
fi

restant=$(comm -23 <(sort ids_tous.txt) <(sort reindex_fait.txt) | wc -l)
echo "Il reste $restant document(s) a faire."
