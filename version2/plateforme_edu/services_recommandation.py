# -*- coding: utf-8 -*-
"""
Service de recommandation.

Deux étapes, dans l'ordre :

1. classifier_apprenants() : regroupe tous les apprenants en 3 groupes
   (débutant / moyen / excellent) avec K-means, à partir de leurs
   statistiques (moyenne générale, nombre de quiz passés). C'est la
   même logique que celle décrite dans le mémoire (dataset OULAD, 3
   clusters).

2. generer_recommandations(apprenant) : une fois le niveau connu,
   choisit des ressources adaptées à ce niveau et crée les
   recommandations correspondantes pour cet apprenant.

Utilisation :
    python3 manage.py generer_recommandations
(voir management/commands/generer_recommandations.py)
"""

import numpy as np
import skfuzzy as fuzz

from .models import Apprenant, Recommandation, Ressource, Statistiques


def classifier_apprenants():
    """
    Regroupe tous les apprenants ayant des statistiques en 3 groupes
    avec la méthode floue (Fuzzy C-means), met à jour leur champ
    `niveau` selon leur groupe dominant, et enregistre le degré
    d'appartenance à chacun des 3 groupes.

    Retourne le nombre d'apprenants reclassés.
    """
    # On récupère toutes les statistiques existantes, avec l'apprenant
    # lié à chacune (select_related évite une requête SQL par apprenant).
    statistiques = list(Statistiques.objects.select_related("apprenant").all())

    if len(statistiques) < 3:
        # Il faut au moins 3 apprenants pour former 3 groupes distincts.
        # En dessous, on ne touche à rien plutôt que de produire un
        # résultat absurde (ex : tout le monde dans le même groupe).
        return 0

    # On construit un tableau numérique à 2 colonnes : la moyenne
    # générale et le nombre de quiz passés, une ligne par apprenant.
    # C'est la même logique que pour K-means, juste avec un algorithme
    # de classification différent ensuite.
    donnees = np.array([
        [float(s.moyenne_generale), s.nombre_quiz_passes]
        for s in statistiques
    ])

    # fuzz.cluster.cmeans() est la fonction du Fuzzy C-means. Elle
    # attend les données transposées (variables en lignes, étudiants
    # en colonnes), d'où le ".T".
    #   - c=3      : on veut 3 groupes, comme K-means
    #   - m=2      : le "degré de flou" standard (valeur usuelle en pratique)
    #   - seed=42  : pour que le résultat soit reproductible d'un lancement à l'autre
    #
    # Elle renvoie :
    #   - centres            : la position des 3 centres de groupe
    #   - degres_appartenance : pour chaque étudiant, son degré
    #                           d'appartenance (entre 0 et 1) à
    #                           CHACUN des 3 groupes (pas un seul comme K-means)
    centres, degres_appartenance, _, _, _, _, _ = fuzz.cluster.cmeans(
        donnees.T,
        c=3,
        m=2,
        error=0.005,
        maxiter=1000,
        seed=42,
    )

    # Pour la classification finale (le champ `niveau`), on retient le
    # groupe DOMINANT de chaque étudiant : celui où son degré
    # d'appartenance est le plus élevé. argmax donne l'index de ce
    # groupe dominant, pour chaque colonne (= chaque étudiant).
    groupes = np.argmax(degres_appartenance, axis=0)

    # Comme pour K-means, les 3 groupes calculés n'ont pas de nom, juste
    # des index (0, 1, 2) qui peuvent sortir dans n'importe quel ordre
    # d'un calcul à l'autre. On les trie donc par moyenne générale du
    # centre du groupe, pour être sûr que "débutant" correspond
    # toujours au groupe le plus faible, "excellent" au plus fort.
    ordre_centres = np.argsort(centres[:, 0])
    cluster_debutant, cluster_moyen, cluster_excellent = ordre_centres
    etiquette_par_cluster = {
        cluster_debutant: Apprenant.niveau.field.choices[0][0],
        cluster_moyen: Apprenant.niveau.field.choices[1][0],
        cluster_excellent: Apprenant.niveau.field.choices[2][0],
    }

    nombre_maj = 0
    for i, (stat, cluster) in enumerate(zip(statistiques, groupes)):
        # Le niveau (groupe dominant) de cet étudiant, correctement
        # étiqueté grâce au tri fait juste au-dessus.
        nouveau_niveau = etiquette_par_cluster[cluster]

        # On enregistre les 3 pourcentages d'appartenance de cet
        # étudiant (dans le bon ordre débutant/moyen/excellent, pas
        # l'ordre brut renvoyé par cmeans). degres_appartenance[X, i]
        # est un nombre entre 0 et 1, donc on multiplie par 100 pour
        # avoir un vrai pourcentage.
        stat.degre_debutant = round(float(degres_appartenance[cluster_debutant, i]) * 100, 2)
        stat.degre_moyen = round(float(degres_appartenance[cluster_moyen, i]) * 100, 2)
        stat.degre_excellent = round(float(degres_appartenance[cluster_excellent, i]) * 100, 2)
        stat.save(update_fields=["degre_debutant", "degre_moyen", "degre_excellent"])

        # On ne met à jour le niveau (et on ne compte le changement)
        # que si le groupe dominant a réellement changé par rapport à
        # avant, pour éviter des écritures en base inutiles.
        if stat.apprenant.niveau != nouveau_niveau:
            stat.apprenant.niveau = nouveau_niveau
            stat.apprenant.save(update_fields=["niveau"])
            nombre_maj += 1

    return nombre_maj

def generer_recommandations(apprenant, nombre_max=3):
    """
    Crée jusqu'à `nombre_max` recommandations pour un apprenant,
    en choisissant des ressources adaptées à son niveau actuel,
    parmi celles de ses parcours, qu'il n'a pas déjà reçues.
    """
    parcours_de_lapprenant = apprenant.inscriptions.values_list("parcours_id", flat=True)

    deja_recommandees = apprenant.recommandations.values_list("ressource_id", flat=True)

    ressources_candidates = (
        Ressource.objects
        .filter(espace__parcours__in=parcours_de_lapprenant)
        .filter(niveau_requis=apprenant.niveau)
        .exclude(id_ressource__in=deja_recommandees)
        .order_by("?")[:nombre_max]
    )

    recommandations_creees = []
    for ressource in ressources_candidates:
        reco = Recommandation.objects.create(
            apprenant=apprenant,
            ressource=ressource,
            groupe=apprenant.niveau,
        )
        recommandations_creees.append(reco)

    return recommandations_creees


def rafraichir_toutes_les_recommandations():
    """
    Fonction "tout-en-un" : reclasse tous les apprenants, puis
    génère de nouvelles recommandations pour chacun. C'est celle-ci
    qu'appelle la commande de gestion.
    """
    nombre_reclasses = classifier_apprenants()

    total_recommandations = 0
    for apprenant in Apprenant.objects.select_related("utilisateur"):
        recos = generer_recommandations(apprenant)
        total_recommandations += len(recos)

    return {
        "apprenants_reclasses": nombre_reclasses,
        "recommandations_creees": total_recommandations,
    }
