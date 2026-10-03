# -*- coding: utf-8 -*-
"""
Modèles Django de la plateforme d'assistance pédagogique.
Basé sur le diagramme de classe (16 classes, 4 groupes) :
  1. Structure pédagogique : Etablissement -> Parcours -> Espace -> Ressources (Quiz/Video/Document)
  2. Acteurs : Utilisateur -> Administrateur / Enseignant / Apprenant
  3. Suivi de performance : Inscription, Evaluation, Statistiques
  4. Intelligence artificielle : Recommandation, AssistanteIA
"""

import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


# =====================================================================
# GROUPE 1 : STRUCTURE PEDAGOGIQUE
# =====================================================================

class Etablissement(models.Model):
    """Un établissement scolaire (ex : un lycée, une université)."""

    id_etab = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=150)
    localite = models.CharField(max_length=150)
    date_creation = models.DateTimeField(auto_now_add=True)
    code_inscription = models.CharField(
        max_length=8, unique=True, editable=False, blank=True,
        help_text="Code à communiquer aux apprenants pour qu'ils puissent s'inscrire dans cet établissement.",
    )

    def save(self, *args, **kwargs):
        if not self.code_inscription:
            import random
            import string
            while True:
                code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                if not Etablissement.objects.filter(code_inscription=code).exists():
                    self.code_inscription = code
                    break
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Établissement"
        verbose_name_plural = "Établissements"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Parcours(models.Model):
    """Un parcours de formation proposé par un établissement (ex : Licence Info)."""

    id_parcours = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.CASCADE, related_name="parcours"
    )
    intitule = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Parcours"
        verbose_name_plural = "Parcours"
        ordering = ["intitule"]

    def __str__(self):
        return self.intitule


class Espace(models.Model):
    """Un espace de cours à l'intérieur d'un parcours (ex : matière / module)."""

    id_espace = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parcours = models.ForeignKey(
        Parcours, on_delete=models.CASCADE, related_name="espaces"
    )
    nom = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Espace"
        verbose_name_plural = "Espaces"
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.parcours.intitule})"


class Ressource(models.Model):
    """
    Classe de base pour toute ressource déposée dans un espace.
    Quiz, Video et Document en héritent (héritage multi-tables Django).
    """

    TYPE_QUIZ = "quiz"
    TYPE_VIDEO = "video"
    TYPE_DOCUMENT = "document"
    TYPE_CHOICES = [
        (TYPE_QUIZ, "Quiz"),
        (TYPE_VIDEO, "Vidéo"),
        (TYPE_DOCUMENT, "Document"),
    ]

    NIVEAU_DEBUTANT = "debutant"
    NIVEAU_MOYEN = "moyen"
    NIVEAU_EXCELLENT = "excellent"
    NIVEAU_CHOICES = [
        (NIVEAU_DEBUTANT, "Débutant"),
        (NIVEAU_MOYEN, "Moyen"),
        (NIVEAU_EXCELLENT, "Excellent"),
    ]

    id_ressource = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    espace = models.ForeignKey(
        Espace, on_delete=models.SET_NULL, null=True, blank=True, related_name="ressources",
        help_text=(
            "Laisser vide pour une ressource nationale par défaut (ex : bibliothèque numérique "
            "du MEN), accessible à tout apprenant même sans établissement rattaché."
        ),
    )
    enseignant = models.ForeignKey(
        "Enseignant", on_delete=models.SET_NULL, null=True, related_name="ressources_publiees"
    )
    titre = models.CharField(max_length=200)
    type_ressource = models.CharField(max_length=20, choices=TYPE_CHOICES)
    niveau_requis = models.CharField(
        max_length=20, choices=NIVEAU_CHOICES, default=NIVEAU_MOYEN,
        help_text="Niveau d'apprenant auquel cette ressource est adaptée (utilisé par le moteur de recommandation).",
    )
    matiere = models.CharField(
        max_length=100, blank=True,
        help_text="Matière de la ressource (ex : Mathématiques, Anglais...). Surtout utile pour les ressources nationales, sans espace/parcours pour les classer.",
    )
    source_externe = models.URLField(
        blank=True,
        help_text="URL de la source d'origine, pour une ressource nationale importée (ex : bibliothèque numérique du MEN). Vide pour une ressource déposée par un enseignant.",
    )
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ressource"
        verbose_name_plural = "Ressources"
        ordering = ["-date_ajout"]

    def __str__(self):
        return self.titre


class Quiz(models.Model):
    """Extension d'une ressource de type quiz."""

    ressource = models.OneToOneField(
        Ressource, on_delete=models.CASCADE, primary_key=True, related_name="quiz"
    )
    nombre_questions = models.PositiveIntegerField(default=0)
    duree_minutes = models.PositiveIntegerField(default=10)

    class Meta:
        verbose_name = "Quiz"
        verbose_name_plural = "Quiz"

    def __str__(self):
        return f"Quiz : {self.ressource.titre}"


class Question(models.Model):
    """Une question à choix multiple d'un Quiz."""

    id_question = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    enonce = models.TextField()
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Question"
        verbose_name_plural = "Questions"
        ordering = ["ordre"]

    def __str__(self):
        return self.enonce[:60]


class Choix(models.Model):
    """Une réponse possible à une Question (une seule est correcte)."""

    id_choix = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choix")
    texte = models.CharField(max_length=255)
    est_correct = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Choix"
        verbose_name_plural = "Choix"

    def __str__(self):
        return self.texte


class Video(models.Model):
    """Extension d'une ressource de type vidéo."""

    ressource = models.OneToOneField(
        Ressource, on_delete=models.CASCADE, primary_key=True, related_name="video"
    )
    fichier = models.FileField(upload_to="videos/", blank=True, default="")
    duree_secondes = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Vidéo"
        verbose_name_plural = "Vidéos"

    def __str__(self):
        return f"Vidéo : {self.ressource.titre}"


class Document(models.Model):
    """Extension d'une ressource de type document (support de cours PDF, etc.)."""

    ressource = models.OneToOneField(
        Ressource, on_delete=models.CASCADE, primary_key=True, related_name="document"
    )
    fichier = models.FileField(upload_to="documents/", blank=True, default="")
    nombre_pages = models.PositiveIntegerField(default=0)
    indexe = models.BooleanField(
        default=False,
        help_text="Vrai si le document a été découpé et indexé pour l'assistant IA.",
    )

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"

    def __str__(self):
        return f"Document : {self.ressource.titre}"


class SegmentDocument(models.Model):
    """
    Un segment de ~500 caractères découpé dans un Document, avec son
    embedding (vecteur nomic-embed-text, 768 nombres) — utilisé par le
    RAG de l'assistant IA pour retrouver les passages pertinents d'un
    cours (voir ia_service.py).
    """

    id_segment = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="segments"
    )
    texte = models.TextField()
    embedding = models.JSONField()
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Segment de document"
        verbose_name_plural = "Segments de document"
        ordering = ["document", "ordre"]

    def __str__(self):
        return f"Segment {self.ordre} de {self.document.ressource.titre}"


# =====================================================================
# GROUPE 2 : ACTEURS
# =====================================================================

class Utilisateur(AbstractUser):
    """
    Utilisateur de la plateforme. Hérite du système d'authentification
    Django (gestion du mot de passe, connexion, permissions) et ajoute
    un rôle pour distinguer administrateur / enseignant / apprenant.
    """

    ROLE_ADMIN = "administrateur"
    ROLE_ENSEIGNANT = "enseignant"
    ROLE_APPRENANT = "apprenant"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "Administrateur"),
        (ROLE_ENSEIGNANT, "Enseignant"),
        (ROLE_APPRENANT, "Apprenant"),
    ]

    id_user = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.SET_NULL, null=True, blank=True, related_name="utilisateurs"
    )

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username


class Administrateur(models.Model):
    """Profil administrateur, lié un à un à un utilisateur."""

    utilisateur = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, primary_key=True, related_name="profil_administrateur"
    )

    class Meta:
        verbose_name = "Administrateur"
        verbose_name_plural = "Administrateurs"

    def __str__(self):
        return f"Admin : {self.utilisateur}"


class Enseignant(models.Model):
    """Profil enseignant, lié un à un à un utilisateur."""

    utilisateur = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, primary_key=True, related_name="profil_enseignant"
    )
    matiere_principale = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Enseignant"
        verbose_name_plural = "Enseignants"

    def __str__(self):
        return f"Enseignant : {self.utilisateur}"


class Apprenant(models.Model):
    """Profil apprenant, lié un à un à un utilisateur."""

    utilisateur = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, primary_key=True, related_name="profil_apprenant"
    )
    niveau = models.CharField(
        max_length=20, choices=Ressource.NIVEAU_CHOICES, default=Ressource.NIVEAU_DEBUTANT,
        help_text="Groupe attribué par le regroupement K-means (débutant / moyen / excellent).",
    )

    class Meta:
        verbose_name = "Apprenant"
        verbose_name_plural = "Apprenants"

    def __str__(self):
        return f"Apprenant : {self.utilisateur}"


# =====================================================================
# GROUPE 3 : SUIVI DE PERFORMANCE
# =====================================================================

class Inscription(models.Model):
    """Inscription d'un apprenant à un parcours."""

    id_inscription = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    apprenant = models.ForeignKey(
        Apprenant, on_delete=models.CASCADE, related_name="inscriptions"
    )
    parcours = models.ForeignKey(
        Parcours, on_delete=models.CASCADE, related_name="inscriptions"
    )
    date_inscription = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Inscription"
        verbose_name_plural = "Inscriptions"
        unique_together = ("apprenant", "parcours")
        ordering = ["-date_inscription"]

    def __str__(self):
        return f"{self.apprenant} -> {self.parcours}"


class Evaluation(models.Model):
    """Résultat d'un apprenant à un quiz."""

    id_evaluation = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    apprenant = models.ForeignKey(
        Apprenant, on_delete=models.CASCADE, related_name="evaluations"
    )
    quiz = models.ForeignKey(
        Quiz, on_delete=models.CASCADE, related_name="evaluations"
    )
    note = models.DecimalField(max_digits=5, decimal_places=2)
    date_passage = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Évaluation"
        verbose_name_plural = "Évaluations"
        ordering = ["-date_passage"]

    def __str__(self):
        return f"{self.apprenant} - {self.quiz} : {self.note}"


class Statistiques(models.Model):
    """
    Statistiques agrégées d'un apprenant, recalculées à partir de ses
    évaluations (moyenne, progression, etc.).
    """

    id_stat = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    apprenant = models.OneToOneField(
        Apprenant, on_delete=models.CASCADE, related_name="statistiques"
    )
    moyenne_generale = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    degre_debutant = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Pourcentage d'appartenance au groupe débutant (méthode floue).",
    )
    degre_moyen = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Pourcentage d'appartenance au groupe moyen (méthode floue).",
    )
    degre_excellent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Pourcentage d'appartenance au groupe excellent (méthode floue).",
    )
    nombre_quiz_passes = models.PositiveIntegerField(default=0)
    derniere_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Statistiques"
        verbose_name_plural = "Statistiques"

    def __str__(self):
        return f"Stats de {self.apprenant}"

    def recalculer(self):
        """Recalcule la moyenne et le nombre de quiz à partir des évaluations."""
        evaluations = self.apprenant.evaluations.all()
        self.nombre_quiz_passes = evaluations.count()
        if self.nombre_quiz_passes:
            total = sum(e.note for e in evaluations)
            self.moyenne_generale = total / self.nombre_quiz_passes
        else:
            self.moyenne_generale = 0
        self.save()


# =====================================================================
# GROUPE 4 : INTELLIGENCE ARTIFICIELLE
# =====================================================================

class Recommandation(models.Model):
    """
    Recommandation générée pour un apprenant (ex : par regroupement
    K-means sur ses statistiques : débutant / moyen / excellent).
    """

    id_recommandation = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    apprenant = models.ForeignKey(
        Apprenant, on_delete=models.CASCADE, related_name="recommandations"
    )
    ressource = models.ForeignKey(
        Ressource, on_delete=models.CASCADE, related_name="recommandations"
    )
    groupe = models.CharField(
        max_length=50,
        blank=True,
        help_text="Groupe attribué par le regroupement (ex : débutant, moyen, excellent).",
    )
    date_generation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Recommandation"
        verbose_name_plural = "Recommandations"
        ordering = ["-date_generation"]

    def __str__(self):
        return f"Recommandation pour {self.apprenant} : {self.ressource}"


class AssistanteIA(models.Model):
    """
    Trace d'un échange entre un apprenant et l'assistant IA, à propos
    d'une ressource (document indexé) éventuellement associée.
    """

    id_echange = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation_id = models.UUIDField(
        null=True, blank=True, db_index=True,
        help_text="Regroupe les échanges d'une même conversation (même valeur tant que l'apprenant ne clique pas sur « Nouvelle conversation »).",
    )
    apprenant = models.ForeignKey(
        Apprenant, on_delete=models.CASCADE, related_name="echanges_ia"
    )
    ressource = models.ForeignKey(
        Ressource, on_delete=models.SET_NULL, null=True, blank=True, related_name="echanges_ia"
    )
    document_joint = models.FileField(
        upload_to="documents_ia/", blank=True, null=True,
        help_text="Document importé directement dans la conversation (bouton « + »), pour que l'assistant l'utilise dans sa réponse.",
    )
    question = models.TextField()
    reponse = models.TextField()
    modele_utilise = models.CharField(max_length=50, blank=True)
    temps_reponse_secondes = models.FloatField(
        null=True, blank=True,
        help_text="Durée entre l'envoi de la question et la réponse complète (recherche RAG + génération) — utile pour comparer les performances entre machines (ex : ordinateur de dev vs Raspberry Pi).",
    )
    date_echange = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Échange assistant IA"
        verbose_name_plural = "Échanges assistant IA"
        ordering = ["-date_echange"]

    def __str__(self):
        return f"Échange IA - {self.apprenant} ({self.date_echange:%d/%m/%Y})"
