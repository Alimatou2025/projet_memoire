from django.db import models

class Conversation(models.Model):
    session_id = models.CharField(max_length=100)
    titre = models.CharField(max_length=100, default="Nouvelle discussion")
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation']

    def __str__(self):
        return self.titre


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20)  # "user" ou "assistant"
    contenu = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date']


class Document(models.Model):
    """Un PDF déposé par un enseignant, associé à une matière.
    La matière détermine quel modèle IA répondra sur ce document."""

    MATIERE_CHOICES = [
        ("maths_pc_svt", "Maths / Physique-Chimie / SVT"),
        ("generation_resume", "Génération / Résumé"),
        ("histoire_geo", "Histoire / Géographie"),
    ]

    doc_id = models.CharField(max_length=64, unique=True)
    titre = models.CharField(max_length=200)
    matiere = models.CharField(max_length=30, choices=MATIERE_CHOICES, default="generation_resume")
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_ajout']

    def __str__(self):
        return f"{self.titre} ({self.get_matiere_display()})"


class Recommandation(models.Model):
    """Correspond exactement à la classe Recommandation du diagramme de
    classes (id_reco, date_generation, cluster, profilApp, generer()).
    Les champs supplémentaires ci-dessous (nb_interactions, score_moyen...)
    sont les données brutes nécessaires au calcul du clustering — elles
    n'apparaissent pas dans le diagramme de classes, qui documente la
    structure conceptuelle, pas les données intermédiaires d'implémentation."""
    SOURCE_CHOICES = [
        ("oulad", "OULAD (validation externe)"),
        ("plateforme", "Plateforme (données réelles)"),
    ]
    PROFIL_CHOICES = [
        ("debutant", "Débutant"),
        ("moyen", "Moyen"),
        ("excellent", "Excellent"),
    ]

    id_reco = models.AutoField(primary_key=True)
    date_generation = models.DateTimeField(auto_now=True)
    cluster = models.IntegerField(null=True, blank=True)
    profilApp = models.CharField(max_length=20, choices=PROFIL_CHOICES, null=True, blank=True)

    identifiant = models.CharField(max_length=64, unique=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="oulad")
    nb_interactions = models.IntegerField(default=0)
    score_moyen = models.FloatField(null=True, blank=True)
    ponctualite_moyenne = models.FloatField(null=True, blank=True)
    charge_travail = models.FloatField(null=True, blank=True)
    nb_tentatives_precedentes = models.IntegerField(default=0)

    class Meta:
        ordering = ['profilApp', '-nb_interactions']

    def __str__(self):
        return f"{self.identifiant} ({self.get_profilApp_display() or 'non classé'})"

    def generer(self):
        """Correspond à la méthode generer() du diagramme de classes."""
        self.save()

    @staticmethod
    def recommandation_pour_profil(profil_nom):
        textes = {
            "debutant": "Privilégier des ressources courtes et guidées, avec des résumés automatiques et des explications pas à pas de l'assistant IA.",
            "moyen": "Proposer des quiz réguliers pour consolider les acquis et encourager l'exploration de ressources complémentaires.",
            "excellent": "Suggérer des ressources plus approfondies et des défis, avec un accompagnement plus léger de l'assistant IA.",
        }
        return textes.get(profil_nom, "")
