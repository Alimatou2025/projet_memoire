"""
Configuration centralisée des versions testées pour le chapitre
d'expérimentation. Change uniquement la valeur de VERSION_ACTIVE pour
basculer d'une version à l'autre — le reste du code (ia_service.py,
views.py) lit cette configuration plutôt que d'avoir le comportement
"codé en dur".
"""

CONFIGURATIONS = {

    # --- Version 1 : un seul modèle à la fois, testé isolément ---
    "v1a_deepseek_seul": {
        "description": "RAG + DeepSeek-r1 seul (pas de routage)",
        "routage_actif": False,
        "modele_unique": "deepseek-r1:1.5b",
    },
    "v1b_qwen_seul": {
        "description": "RAG + Qwen2.5 seul (pas de routage)",
        "routage_actif": False,
        "modele_unique": "qwen2.5:1.5b",
    },
    "v1c_gemma_seul": {
        "description": "RAG + Gemma2 seul (pas de routage)",
        "routage_actif": False,
        "modele_unique": "gemma2:2b",
    },

    # --- Version 2 : deux modèles, routage simple à 2 catégories ---
    "v2_deux_modeles": {
        "description": "RAG + routage à 2 catégories (scientifique / autre)",
        "routage_actif": True,
        "categories": {
            "scientifique": "deepseek-r1:1.5b",
            "autre": "qwen2.5:1.5b",
        },
        "secours_mots_cles": False,
        "garde_fous": False,
    },

    # --- Version 3 : trois modèles, routage complet mais sans filet de secours ---
    "v3_trois_modeles": {
        "description": "RAG + routage à 3 catégories, sans secours mots-clés",
        "routage_actif": True,
        "categories": {
            "maths_pc_svt": "deepseek-r1:1.5b",
            "histoire_geo": "qwen2.5:1.5b",
            "generation_resume": "gemma2:2b",
        },
        "secours_mots_cles": False,
        "garde_fous": False,
    },

    # --- Version 4 : le système complet actuel ---
    "v4_routage_complet": {
        "description": "RAG + routage complet (3 modèles + secours + garde-fous)",
        "routage_actif": True,
        "categories": {
            "maths_pc_svt": "deepseek-r1:1.5b",
            "histoire_geo": "qwen2.5:1.5b",
            "generation_resume": "gemma2:2b",
        },
        "secours_mots_cles": True,
        "garde_fous": True,
    },
}

# ★ Change UNIQUEMENT cette ligne pour changer de version à tester.
VERSION_ACTIVE = "v3_trois_modeles"


def config_actuelle():
    """Renvoie le dictionnaire de configuration de la version actuellement
    sélectionnée — c'est cette fonction que le reste du code doit appeler,
    plutôt que de coder un comportement fixe."""
    return CONFIGURATIONS[VERSION_ACTIVE]
