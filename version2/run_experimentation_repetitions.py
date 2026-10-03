"""
Script d'exécution de l'expérimentation du Chapitre 4 — version avec
répétitions.

Chaque question est maintenant posée plusieurs fois de suite (voir
NB_REPETITIONS ci-dessous), pas une seule fois comme dans la première
version de ce script. Ça permet de calculer un temps moyen plus fiable, et
de voir si un modèle répond de façon stable ou si ses réponses varient
d'un essai à l'autre sur une même question.
"""

import csv
import subprocess
import time

import requests

from config_experimentation import VERSION_ACTIVE
from questions_test import QUESTIONS_TEST

URL_SERVEUR_TEST = "http://localhost:8001/assistant_ia/"
NOM_CONTENEUR_OLLAMA = "memoire_ia"

# ★ Nombre de fois où chaque question est reposée, pour vérifier la
# stabilité des réponses. 3 est un bon compromis entre rigueur et temps
# disponible (5 questions x 3 répétitions = 15 appels par version, au lieu
# de 5 dans la première version du script).
NB_REPETITIONS = 3


def mesurer_ram_ollama():
    try:
        resultat = subprocess.run(
            ["free", "-m"],
            capture_output=True, text=True, timeout=10
        )
        ligne_mem = resultat.stdout.splitlines()[1]
        ram_utilisee_mo = ligne_mem.split()[2]
        return f"{ram_utilisee_mo} Mo"
    except Exception as e:
        return f"Erreur mesure RAM : {e}"


def poser_une_question(question_test):
    donnees = {"question": question_test["question"]}
    if question_test.get("doc_id"):
        donnees["doc_id"] = question_test["doc_id"]

    debut = time.time()
    try:
        reponse_http = requests.post(URL_SERVEUR_TEST, data=donnees, timeout=180)
        temps_ecoule = time.time() - debut
        reponse_json = reponse_http.json()
        texte_reponse = reponse_json.get("reponse", "ERREUR : pas de champ 'reponse'")
    except Exception as e:
        temps_ecoule = time.time() - debut
        texte_reponse = f"ERREUR : {e}"

    return temps_ecoule, texte_reponse


def executer_tous_les_tests():
    nom_fichier_sortie = f"resultats_{VERSION_ACTIVE}_repetitions.csv"

    print(f"{'='*60}")
    print(f"DÉBUT DES TESTS — VERSION : {VERSION_ACTIVE}")
    print(f"Chaque question sera posée {NB_REPETITIONS} fois")
    print(f"{'='*60}\n")

    with open(nom_fichier_sortie, "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.writer(f, delimiter=";")
        ecrivain.writerow(["version", "id_question", "repetition", "question",
                            "temps_secondes", "ram", "reponse"])

        for question_test in QUESTIONS_TEST:
            temps_des_repetitions = []

            for numero_repetition in range(1, NB_REPETITIONS + 1):
                print(f"→ {question_test['id']} (essai {numero_repetition}/{NB_REPETITIONS})")

                temps, texte_reponse = poser_une_question(question_test)
                ram = mesurer_ram_ollama()
                temps_des_repetitions.append(temps)

                print(f"  Temps : {temps:.2f}s")
                print(f"  Réponse : {texte_reponse[:120]}...\n")

                ecrivain.writerow([
                    VERSION_ACTIVE,
                    question_test["id"],
                    numero_repetition,
                    question_test["question"],
                    f"{temps:.2f}",
                    ram,
                    texte_reponse,
                ])

                time.sleep(3)

            moyenne = sum(temps_des_repetitions) / len(temps_des_repetitions)
            ecart = max(temps_des_repetitions) - min(temps_des_repetitions)
            print(f"  ➜ Moyenne pour {question_test['id']} : {moyenne:.2f}s "
                  f"(écart entre le plus rapide et le plus lent : {ecart:.2f}s)\n")

    print(f"{'='*60}")
    print(f"TESTS TERMINÉS. Résultats enregistrés dans : {nom_fichier_sortie}")
    print(f"{'='*60}")


if __name__ == "__main__":
    executer_tous_les_tests()
