"""
Banque de questions utilisées pour l'expérimentation du Chapitre 4.

Ce fichier ne contient QUE les données de test — aucune logique d'exécution
ici. Le même jeu de questions est utilisé, sans aucune modification, pour
chacune des 7 versions testées, ce qui garantit une comparaison équitable.

Pour ajouter, retirer ou modifier une question de test, c'est ICI et
seulement ici qu'il faut le faire — jamais dans le script d'exécution.
"""

QUESTIONS_TEST = [
    {
        # Cette question teste le raisonnement scientifique pur, sans
        # aucun document de cours pour s'appuyer dessus — le cas le plus
        # à risque d'hallucination pour un petit modèle.
        "id": "Q1_maths_sans_contexte",
        "question": "Quelle est la formule de l'aire d'un cercle ?",
        "doc_id": None,
        "type": "Raisonnement scientifique, sans document de cours",
    },
    {
        # Teste une connaissance factuelle générale (pas de raisonnement,
        # juste un fait à connaître), toujours sans document de cours.
        "id": "Q2_histgeo_sans_contexte",
        "question": "Quelle est la capitale du Sénégal ?",
        "doc_id": None,
        "type": "Connaissance factuelle, sans document de cours",
    },
    {
        # Question volontairement vague ("le triangle" n'a pas "une seule"
        # formule), pour voir comment le système réagit à l'ambiguïté.
        "id": "Q3_question_ambigue",
        "question": "Je veux la formule du triangle",
        "doc_id": None,
        "type": "Question ouverte/imprécise",
    },
    {
        # LE cas normal d'usage de la plateforme : un vrai document est
        # déjà indexé, le RAG doit donc trouver du contenu pertinent.
        "id": "Q4_avec_contexte_rag",
        "question": "Que retenir de ce cours ?",
        "doc_id": "abc9ecc7-31d4-4fbd-906e-664959b9a369",
        "type": "Usage normal, avec un document de cours réellement indexé",
    },
    {
        # Cette question seule ("Et pour un cercle ?") n'a aucun sens sans
        # l'historique fourni ci-dessous — elle teste si le système sait
        # bien utiliser la conversation précédente pour se repérer.
        "id": "Q5_question_de_suivi",
        "question": "Et pour un cercle ?",
        "doc_id": None,
        "type": "Gestion de l'historique de conversation",
        "historique": [
            {"role": "user", "content": "Comment calculer l'aire d'un triangle ?"},
            {"role": "assistant", "content": "L'aire d'un triangle se calcule avec base × hauteur ÷ 2."},
        ],
    },
]
