"""
Script d'exécution de l'expérimentation du Chapitre 4.

Rôle unique de ce fichier : lire la configuration active
(config_experimentation.py) et la banque de questions (questions_test.py),
envoyer chaque question au serveur de test, mesurer le temps de réponse et
la RAM utilisée par Ollama, puis écrire un fichier CSV propre — un fichier
par version testée.

Aucune donnée de test ni aucun réglage système n'est codé ici : ce script
se contente d'exécuter, à partir des données fournies par les deux autres
fichiers.

Usage :
    python3 run_experimentation.py
"""

import csv
import subprocess
import time

import requests

# On importe la version actuellement active (juste le nom, en texte) et la
# liste des questions, depuis les deux autres fichiers séparés.
from config_experimentation import VERSION_ACTIVE
from questions_test import QUESTIONS_TEST

# Adresse du serveur de test (la copie séparée, sur le port 8001, pas la
# vraie plateforme qui tourne sur 8000).
URL_SERVEUR_TEST = "http://localhost:8001/assistant_ia/"

# Nom du conteneur Docker qui fait tourner Ollama, pour pouvoir mesurer sa
# RAM avec "docker stats".
NOM_CONTENEUR_OLLAMA = "memoire_ia"


def mesurer_ram_ollama():
    # docker stats ne fonctionne pas sur ce Raspberry Pi (cgroup mémoire
    # désactivé par défaut), donc on mesure la RAM globale du système avec
    # free -m à la place.
    try:
        resultat = subprocess.run(
            ["free", "-m"],
            capture_output=True, text=True, timeout=10
        )
        ligne_mem = resultat.stdout.splitlines()[1]
        ram_utilisee_mo = ligne_mem.split()[2]
        return f"{ram_utilisee_mo} Mo (RAM systeme totale)"
    except Exception as e:
        return f"Erreur mesure RAM : {e}"


def poser_une_question(question_test):
    # On prépare les données à envoyer au serveur : toujours la question,
    # et le doc_id seulement si cette question précise en a besoin
    # (certaines questions du jeu de test n'en ont pas, comme "capitale du
    # Sénégal").
    donnees = {"question": question_test["question"]}
    if question_test.get("doc_id"):
        donnees["doc_id"] = question_test["doc_id"]

    # time.time() donne l'heure actuelle en secondes. On la note juste
    # avant d'envoyer la question, et on la reprendra juste après avoir
    # reçu la réponse, pour calculer le temps écoulé entre les deux.
    debut = time.time()
    try:
        # requests.post() envoie une vraie requête HTTP, comme le ferait
        # un navigateur en cliquant sur "Envoyer" sur la plateforme.
        reponse_http = requests.post(URL_SERVEUR_TEST, data=donnees, timeout=180)
        temps_ecoule = time.time() - debut
        reponse_json = reponse_http.json()
        texte_reponse = reponse_json.get("reponse", "ERREUR : pas de champ 'reponse'")
    except Exception as e:
        # Si le serveur ne répond pas du tout (crash, timeout dépassé...),
        # on capture quand même le temps écoulé jusqu'à l'échec, et on note
        # clairement que c'est une erreur dans la réponse enregistrée.
        temps_ecoule = time.time() - debut
        texte_reponse = f"ERREUR : {e}"

    return temps_ecoule, texte_reponse


def executer_tous_les_tests():
    # Le nom du fichier de sortie s'adapte automatiquement à la version
    # actuellement configurée — pas besoin de le changer à la main à
    # chaque fois, il suffit de changer VERSION_ACTIVE dans l'autre fichier.
    nom_fichier_sortie = f"resultats_{VERSION_ACTIVE}.csv"

    print(f"{'='*60}")
    print(f"DÉBUT DES TESTS — VERSION : {VERSION_ACTIVE}")
    print(f"{'='*60}\n")

    # "with open(...)" ouvre le fichier et le referme automatiquement à la
    # fin, même si une erreur survient en cours de route — plus sûr que
    # d'ouvrir/fermer le fichier à la main.
    with open(nom_fichier_sortie, "w", newline="", encoding="utf-8") as f:
        # csv.writer gère automatiquement les cas compliqués (guillemets,
        # points-virgules dans le texte...) qui posaient problème avec le
        # premier script en bash.
        ecrivain = csv.writer(f, delimiter=";")

        # On écrit d'abord la ligne d'en-tête, avec le nom de chaque colonne.
        ecrivain.writerow(["version", "id_question", "question", "type_teste",
                            "temps_secondes", "ram_ollama", "reponse"])

        # On parcourt chaque question du fichier questions_test.py, une par
        # une, dans l'ordre où elles sont écrites.
        for question_test in QUESTIONS_TEST:
            print(f"→ {question_test['id']} : {question_test['question']}")

            temps, texte_reponse = poser_une_question(question_test)
            ram = mesurer_ram_ollama()

            # :.2f affiche le nombre avec seulement 2 chiffres après la
            # virgule, plus lisible que tous les chiffres bruts.
            print(f"  Temps : {temps:.2f}s | RAM : {ram}")
            # [:150] ne garde que les 150 premiers caractères de la
            # réponse pour l'affichage dans le terminal (sinon ce serait
            # trop long à lire) — le fichier CSV, lui, garde la réponse
            # complète, sans coupure.
            print(f"  Réponse : {texte_reponse[:150]}...\n")

            ecrivain.writerow([
                VERSION_ACTIVE,
                question_test["id"],
                question_test["question"],
                question_test["type"],
                f"{temps:.2f}",
                ram,
                texte_reponse,
            ])

            # Petite pause entre chaque question, pour laisser le Pi
            # "respirer" un peu avant la question suivante, plutôt que
            # d'enchaîner immédiatement (ce qui pourrait fausser la mesure
            # de RAM/temps de la question suivante).
            time.sleep(3)

    print(f"{'='*60}")
    print(f"TESTS TERMINÉS. Résultats enregistrés dans : {nom_fichier_sortie}")
    print(f"{'='*60}")


# Cette ligne fait que le script ne s'exécute que si on le lance
# directement (python3 run_experimentation.py), pas s'il est juste importé
# depuis un autre fichier Python.
if __name__ == "__main__":
    executer_tous_les_tests()
