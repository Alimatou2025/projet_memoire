"""
Commande : python manage.py generer_recommandations

Télécharge un échantillon réel du jeu de données OULAD (Open University
Learning Analytics Dataset, 32 593 étudiants réels, licence CC-BY 4.0),
construit des profils comportementaux, applique un clustering K-means en
3 groupes (débutant/moyen/excellent), et enregistre le résultat dans la
table Recommandation.

Ce jeu de données sert de validation externe de la méthode de clustering,
en attendant qu'un volume suffisant de données réelles issues de la
plateforme elle-même soit disponible (voir mémoire, section Recommandation).
"""

import io
import urllib.request
import pandas as pd
import numpy as np
from django.core.management.base import BaseCommand
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from plateforme_edu.models import Recommandation

URL_BASE = "https://raw.githubusercontent.com/marloft/MachineLearning/master/Documents/ML/PhD/Datasets/Open%20University%20Learning%20Analytics%20Dataset%20-%20OULAD/"
TAILLE_ECHANTILLON = 3000
SEED = 42


class Command(BaseCommand):
    help = "Génère les recommandations (clustering K-means) à partir du jeu de données réel OULAD."

    def add_arguments(self, parser):
        parser.add_argument(
            "--taille",
            type=int,
            default=TAILLE_ECHANTILLON,
            help="Taille de l'échantillon OULAD à utiliser (par défaut 3000).",
        )

    def telecharger_csv(self, nom_fichier):
        url = URL_BASE + nom_fichier
        self.stdout.write(f"Téléchargement de {nom_fichier}...")
        with urllib.request.urlopen(url, timeout=60) as reponse:
            contenu = reponse.read()
        return pd.read_csv(io.BytesIO(contenu))

    def handle(self, *args, **options):
        taille = options["taille"]
        np.random.seed(SEED)

        student_info = self.telecharger_csv("studentInfo.csv")
        student_assessment = self.telecharger_csv("studentAssessment.csv")
        assessments = self.telecharger_csv("assessments.csv")
        self.stdout.write(self.style.SUCCESS(
            f"{student_info['id_student'].nunique()} étudiants réels chargés (OULAD)."
        ))

        merged = student_assessment.merge(
            assessments[["id_assessment", "date"]], on="id_assessment", how="left"
        )
        merged["retard"] = merged["date_submitted"] - merged["date"]

        features = merged.groupby("id_student").agg(
            nb_interactions=("id_assessment", "count"),
            score_moyen=("score", "mean"),
            ponctualite_moyenne=("retard", "mean"),
        ).reset_index()

        info_uniques = student_info.drop_duplicates(subset="id_student")[
            ["id_student", "studied_credits", "num_of_prev_attempts"]
        ]
        df = features.merge(info_uniques, on="id_student", how="inner").dropna()
        df = df.rename(columns={"studied_credits": "charge_travail",
                                 "num_of_prev_attempts": "nb_tentatives_precedentes"})

        if len(df) > taille:
            df = df.sample(n=taille, random_state=SEED).reset_index(drop=True)
        self.stdout.write(f"{len(df)} profils comportementaux réels retenus pour le clustering.")

        colonnes = ["nb_interactions", "score_moyen", "ponctualite_moyenne",
                    "charge_travail", "nb_tentatives_precedentes"]
        X = df[colonnes].values
        X_scaled = StandardScaler().fit_transform(X)

        kmeans = KMeans(n_clusters=3, random_state=SEED, n_init=10)
        df["cluster"] = kmeans.fit_predict(X_scaled)
        score_silhouette = silhouette_score(X_scaled, df["cluster"])
        self.stdout.write(f"Score de silhouette : {score_silhouette:.3f}")

        ordre_clusters = df.groupby("cluster")["score_moyen"].mean().sort_values().index.tolist()
        noms_profils = ["debutant", "moyen", "excellent"]
        mapping = {cluster_id: noms_profils[i] for i, cluster_id in enumerate(ordre_clusters)}
        df["profil_nom"] = df["cluster"].map(mapping)

        Recommandation.objects.filter(source="oulad").delete()
        objets = [
            Recommandation(
                identifiant=f"oulad_{row.id_student}",
                source="oulad",
                nb_interactions=int(row.nb_interactions),
                score_moyen=float(row.score_moyen),
                ponctualite_moyenne=float(row.ponctualite_moyenne),
                charge_travail=float(row.charge_travail),
                nb_tentatives_precedentes=int(row.nb_tentatives_precedentes),
                cluster=int(row.cluster),
                profilApp=row.profil_nom,
            )
            for row in df.itertuples()
        ]
        Recommandation.objects.bulk_create(objets)

        self.stdout.write(self.style.SUCCESS(
            f"{len(objets)} recommandations générées et enregistrées avec succès."
        ))
        for profil in noms_profils:
            n = df[df["profil_nom"] == profil].shape[0]
            self.stdout.write(f"  - {profil} : {n} apprenants")
