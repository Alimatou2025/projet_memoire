# -*- coding: utf-8 -*-
"""
Vues d'authentification et redirection selon le rôle.

Principe : UNE SEULE page de connexion pour tout le monde.
Après la connexion, on regarde le champ `role` de l'utilisateur
(défini dans models.py, classe Utilisateur) et on l'envoie vers
le bon tableau de bord. C'est cette valeur de `role` qui permet
de savoir si c'est un administrateur, un enseignant ou un apprenant
qui vient de se connecter.
"""

from functools import wraps

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import Utilisateur


def accueil(request):
    """Page d'accueil publique."""
    return render(request, "accueil.html")


def connexion(request):
    """
    Une seule page de connexion. Après vérification du mot de passe,
    on redirige selon request.user.role.
    """
    if request.user.is_authenticated:
        return rediriger_selon_role(request.user)

    if request.method == "POST":
        identifiant = request.POST.get("username")
        mot_de_passe = request.POST.get("password")
        utilisateur = authenticate(request, username=identifiant, password=mot_de_passe)

        if utilisateur is not None:
            login(request, utilisateur)
            return rediriger_selon_role(utilisateur)
        else:
            return render(request, "connexion.html", {
                "erreur": "Identifiant ou mot de passe incorrect."
            })

    return render(request, "connexion.html")


def inscription(request):
    """
    Formulaire d'inscription public. Réservé aux apprenants : les
    enseignants n'ont pas d'auto-inscription, leur compte est créé par
    l'administrateur de leur établissement (voir gerer_utilisateurs), et
    un compte administrateur se crée uniquement via createsuperuser, pour
    des raisons de sécurité (on ne veut pas que n'importe qui puisse
    s'auto-déclarer enseignant ou administrateur en s'inscrivant sur le
    site). L'apprenant doit fournir le code de son établissement pour que
    son compte y soit automatiquement rattaché.
    """
    from .models import Apprenant, Etablissement

    if request.method == "POST":
        code = request.POST.get("code_etablissement", "").strip().upper()
        username = request.POST.get("username")

        etablissement = Etablissement.objects.filter(code_inscription=code).first()
        if etablissement is None:
            return render(request, "inscription.html", {"erreur": "Code d'établissement invalide."})

        if Utilisateur.objects.filter(username=username).exists():
            return render(request, "inscription.html", {"erreur": "Cet identifiant est déjà pris."})

        utilisateur = Utilisateur.objects.create_user(
            username=username,
            email=request.POST.get("email", ""),
            password=request.POST.get("password"),
            first_name=request.POST.get("first_name", ""),
            last_name=request.POST.get("last_name", ""),
            role=Utilisateur.ROLE_APPRENANT,
            etablissement=etablissement,
        )
        Apprenant.objects.create(utilisateur=utilisateur)

        login(request, utilisateur)
        return rediriger_selon_role(utilisateur)

    return render(request, "inscription.html")


def rediriger_selon_role(utilisateur):
    """
    C'est ICI que la plateforme sait qui vient de se connecter :
    on lit utilisateur.role (rempli à la création du compte) et
    on choisit la bonne page. Pas besoin de plusieurs pages de
    connexion : une seule suffit, la distinction se fait après coup.
    """
    if utilisateur.role == Utilisateur.ROLE_ADMIN:
        return redirect("tableau_bord_admin")
    elif utilisateur.role == Utilisateur.ROLE_ENSEIGNANT:
        return redirect("tableau_bord_enseignant")
    elif utilisateur.role == Utilisateur.ROLE_APPRENANT:
        return redirect("tableau_bord_apprenant")
    else:
        return redirect("accueil")


def deconnexion(request):
    logout(request)
    return redirect("accueil")


@login_required
def assistant_ia(request):
    """
    Page de l'assistant IA. À l'ouverture de la page (sans conversation
    précisée dans l'URL), on affiche un écran d'accueil vide — comme sur
    Claude ou ChatGPT — pas automatiquement la dernière conversation.
    Une conversation ne s'affiche que si son identifiant est explicitement
    dans l'URL (?conversation=<uuid>) : soit parce que l'apprenant clique
    dessus dans la barre latérale "Historique", soit parce qu'il vient
    d'envoyer un message (la page se redirige alors vers cette URL précise
    pour qu'il voie la réponse).
    """
    import uuid
    from django.urls import reverse
    from . import ia_service
    from .models import AssistanteIA, Ressource

    profil = getattr(request.user, "profil_apprenant", None)

    if request.method == "POST" and profil is not None and request.POST.get("nouvelle_conversation"):
        return redirect("assistant_ia")

    if request.method == "POST" and profil is not None:
        question = request.POST.get("question", "").strip()
        ressource = None
        ressource_id = request.POST.get("ressource")
        if ressource_id:
            ressource = Ressource.objects.filter(id_ressource=ressource_id).first()

        document_joint = request.FILES.get("document_joint")

        if not question and document_joint:
            question = "Peux-tu m'expliquer ce document : {} ?".format(document_joint.name)

        # Identifiant de la conversation en cours, transmis par le champ
        # caché du formulaire (vide si on vient de l'écran d'accueil).
        conversation_id = request.POST.get("conversation_id") or ""

        if question:
            import time
            debut = time.perf_counter()

            if not conversation_id:
                conversation_id = str(uuid.uuid4())

            derniers_echanges = list(
                profil.echanges_ia.filter(conversation_id=conversation_id)
                .order_by("-date_echange")[:4]
                .values_list("question", "reponse")
            )
            derniers_echanges.reverse()

            passages = []
            try:
                if document_joint is not None:
                    passages = ia_service.rechercher_passages_fichier_televerse(question, document_joint)
                elif ressource is not None and hasattr(ressource, "document") and ressource.document.indexe:
                    passages = ia_service.rechercher_passages_document(question, ressource.document)
                else:
                    # Aucune ressource selectionnee : on cherche directement
                    # dans tout le corpus ChromaDB (interet du RAG).
                    passages = ia_service.rechercher_passages_corpus(question)

                reponse, modele_utilise = ia_service.generer_reponse(question, passages, derniers_echanges)
            except ia_service.ErreurServiceIA:
                reponse = (
                    "Désolé, je n'ai pas pu contacter le service IA local (Ollama). "
                    "Vérifie que le conteneur `memoire_ia` tourne bien, puis réessaie."
                )
                modele_utilise = ""

            temps_reponse = round(time.perf_counter() - debut, 2)

            AssistanteIA.objects.create(
                apprenant=profil,
                ressource=ressource,
                document_joint=document_joint,
                question=question,
                reponse=reponse,
                modele_utilise=modele_utilise,
                temps_reponse_secondes=temps_reponse,
                conversation_id=conversation_id,
            )
            return redirect(reverse("assistant_ia") + "?conversation=" + conversation_id)

        return redirect("assistant_ia")

    contexte = {}
    if profil is not None:
        echanges_groupes = {}
        for echange in profil.echanges_ia.exclude(conversation_id__isnull=True).order_by("date_echange"):
            groupe = echanges_groupes.setdefault(echange.conversation_id, {
                "conversation_id": echange.conversation_id,
                "premiere_question": echange.question,
                "derniere_date": echange.date_echange,
                "nombre_echanges": 0,
            })
            groupe["nombre_echanges"] += 1
            groupe["derniere_date"] = echange.date_echange

        contexte["historique_recent"] = sorted(
            echanges_groupes.values(), key=lambda g: g["derniere_date"], reverse=True
        )

        # Écran d'accueil vide par défaut : seule une conversation demandée
        # explicitement dans l'URL est affichée.
        conversation_affichee = request.GET.get("conversation") or ""
        contexte["conversation_active"] = conversation_affichee
        contexte["historique"] = (
            profil.echanges_ia.filter(conversation_id=conversation_affichee).order_by("date_echange")
            if conversation_affichee else profil.echanges_ia.none()
        )

        contexte["ressources_disponibles"] = Ressource.objects.filter(
            espace__parcours__inscriptions__apprenant=profil
        ).distinct()

    return render(request, "assistant_ia.html", contexte)

# ---------------------------------------------------------------------
# Décorateurs pour protéger les vues selon le rôle
# (ex : @exige_role(Utilisateur.ROLE_ADMIN) au-dessus d'une vue admin)
# ---------------------------------------------------------------------

def exige_role(role_attendu):
    """
    Empêche un apprenant d'accéder à une page réservée à l'admin
    (et inversement), même en tapant l'URL directement.
    """
    def decorateur(vue):
        @wraps(vue)
        @login_required
        def vue_protegee(request, *args, **kwargs):
            if request.user.role != role_attendu:
                return redirect("accueil")
            return vue(request, *args, **kwargs)
        return vue_protegee
    return decorateur


@exige_role(Utilisateur.ROLE_ADMIN)
def tableau_bord_admin(request):
    from .models import Parcours, Ressource, AssistanteIA

    etablissement = request.user.etablissement
    contexte = {
        "nombre_utilisateurs": Utilisateur.objects.filter(etablissement=etablissement).count(),
        "nombre_parcours": Parcours.objects.filter(etablissement=etablissement).count(),
        "nombre_ressources": Ressource.objects.filter(espace__parcours__etablissement=etablissement).count(),
        "nombre_echanges_ia": AssistanteIA.objects.count(),
        "derniers_utilisateurs": Utilisateur.objects.filter(etablissement=etablissement).order_by("-date_joined")[:8],
        "parcours_liste": Parcours.objects.filter(etablissement=etablissement),
    }
    return render(request, "tableau_bord_admin.html", contexte)


@exige_role(Utilisateur.ROLE_ENSEIGNANT)
def tableau_bord_enseignant(request):
    from django.db.models import Avg
    from .models import Apprenant, Evaluation

    profil = request.user.profil_enseignant
    ressources = profil.ressources_publiees.all()
    evaluations_enseignant = Evaluation.objects.filter(
        quiz__ressource__enseignant=profil
    )
    dernieres_evaluations = evaluations_enseignant.order_by("-date_passage")[:8]

    apprenants = (
        Apprenant.objects
        .filter(utilisateur__etablissement=request.user.etablissement)
        .select_related("utilisateur", "statistiques")
        .order_by("niveau", "utilisateur__last_name")
    )

    contexte = {
        "ressources": ressources,
        "nombre_ressources": ressources.count(),
        "nombre_apprenants": evaluations_enseignant.values("apprenant").distinct().count(),
        "moyenne_classe": evaluations_enseignant.aggregate(m=Avg("note"))["m"],
        "dernieres_evaluations": dernieres_evaluations,
        "apprenants": apprenants,
    }
    return render(request, "tableau_bord_enseignant.html", contexte)

@exige_role(Utilisateur.ROLE_ADMIN)
def gerer_etablissement(request):
    """
    Permet à l'administrateur de créer (s'il n'en a pas encore) ou de
    modifier les informations de son établissement (nom, localité).
    """
    from django.contrib import messages
    from .models import Etablissement

    etablissement = request.user.etablissement

    if request.method == "POST":
        nom = request.POST.get("nom", "").strip()
        localite = request.POST.get("localite", "").strip()

        if not nom:
            return render(request, "gerer_etablissement.html", {
                "etablissement": etablissement,
                "erreur": "Le nom de l'établissement est obligatoire.",
            })

        if etablissement is None:
            etablissement = Etablissement.objects.create(nom=nom, localite=localite)
            request.user.etablissement = etablissement
            request.user.save(update_fields=["etablissement"])
            messages.success(request, "Établissement créé avec succès.")
        else:
            etablissement.nom = nom
            etablissement.localite = localite
            etablissement.save(update_fields=["nom", "localite"])
            messages.success(request, "Établissement enregistré avec succès.")

        return redirect("gerer_etablissement")

    return render(request, "gerer_etablissement.html", {"etablissement": etablissement})


@exige_role(Utilisateur.ROLE_ADMIN)
def supprimer_etablissement(request):
    """
    Supprime l'établissement de l'administrateur connecté, uniquement
    s'il n'a plus aucun parcours rattaché (pour éviter de perdre en
    cascade des espaces/ressources encore utilisés).
    """
    etablissement = request.user.etablissement

    if request.method == "POST" and etablissement is not None:
        if etablissement.parcours.exists():
            return render(request, "gerer_etablissement.html", {
                "etablissement": etablissement,
                "erreur": (
                    "Impossible de supprimer : cet établissement a encore des "
                    "parcours rattachés. Supprime-les d'abord."
                ),
            })
        request.user.etablissement = None
        request.user.save(update_fields=["etablissement"])
        etablissement.delete()

    return redirect("gerer_etablissement")


@exige_role(Utilisateur.ROLE_ADMIN)
def gerer_utilisateurs(request):
    """
    Liste les utilisateurs de l'établissement de l'administrateur, permet
    d'y créer un compte enseignant (les enseignants ne s'inscrivent pas
    eux-mêmes : c'est l'administrateur de l'établissement qui les ajoute,
    pour éviter que n'importe qui se déclare enseignant d'un établissement
    qui n'est pas le sien) et d'en supprimer un (jamais soi-même).
    """
    from .models import Enseignant

    etablissement = request.user.etablissement
    utilisateurs = Utilisateur.objects.filter(etablissement=etablissement).order_by("role", "last_name")
    erreur = None
    identifiants_crees = None

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "creer_enseignant":
            username = request.POST.get("username", "").strip()
            password = request.POST.get("password", "").strip()
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()

            if not username or not password:
                erreur = "Identifiant et mot de passe obligatoires."
            elif Utilisateur.objects.filter(username=username).exists():
                erreur = "Cet identifiant est déjà pris."
            else:
                nouvel_enseignant = Utilisateur.objects.create_user(
                    username=username,
                    email=request.POST.get("email", "").strip(),
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    role=Utilisateur.ROLE_ENSEIGNANT,
                    etablissement=etablissement,
                )
                Enseignant.objects.create(utilisateur=nouvel_enseignant)
                utilisateurs = Utilisateur.objects.filter(etablissement=etablissement).order_by("role", "last_name")
                # Le mot de passe en clair n'est jamais enregistré (Django ne
                # stocke que sa version hachée) : on l'affiche une seule fois
                # ici, juste après la création, pour que l'administrateur
                # puisse le noter et le transmettre à l'enseignant.
                identifiants_crees = {"username": username, "password": password}

        else:
            cible = utilisateurs.filter(id=request.POST.get("id_utilisateur")).exclude(id=request.user.id).first()
            if cible:
                cible.delete()
            return redirect("gerer_utilisateurs")

    return render(request, "gerer_utilisateurs.html", {
        "utilisateurs": utilisateurs,
        "erreur": erreur,
        "identifiants_crees": identifiants_crees,
    })


@exige_role(Utilisateur.ROLE_ADMIN)
def gerer_parcours(request):
    """
    Liste les parcours de l'établissement de l'administrateur, permet
    d'en créer un nouveau et d'en supprimer un (cascade sur ses espaces
    et ressources).
    """
    from .models import Parcours

    etablissement = request.user.etablissement
    parcours_liste = (
        Parcours.objects.filter(etablissement=etablissement).order_by("intitule")
        if etablissement else Parcours.objects.none()
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "creer" and etablissement is not None:
            intitule = request.POST.get("intitule", "").strip()
            description = request.POST.get("description", "").strip()
            if intitule:
                Parcours.objects.create(etablissement=etablissement, intitule=intitule, description=description)

        elif action == "modifier":
            cible = parcours_liste.filter(id_parcours=request.POST.get("id_parcours")).first()
            if cible:
                intitule = request.POST.get("intitule", "").strip()
                description = request.POST.get("description", "").strip()
                if intitule:
                    cible.intitule = intitule
                    cible.description = description
                    cible.save(update_fields=["intitule", "description"])

        elif action == "supprimer":
            cible = parcours_liste.filter(id_parcours=request.POST.get("id_parcours")).first()
            if cible:
                cible.delete()

        return redirect("gerer_parcours")

    return render(request, "gerer_parcours.html", {
        "parcours_liste": parcours_liste,
        "a_etablissement": etablissement is not None,
    })


@login_required
def mes_ressources(request):
    """
    Page « Mes ressources ». Selon le rôle :
    - l'enseignant y voit ses ressources publiées et peut en ajouter une ;
    - l'apprenant y voit les ressources disponibles dans ses parcours.
    """
    from .models import Choix, Document, Espace, Etablissement, Parcours, Question, Quiz, Ressource

    if request.user.role == Utilisateur.ROLE_ENSEIGNANT:
        profil = request.user.profil_enseignant
        espaces = Espace.objects.filter(parcours__etablissement=request.user.etablissement)

        if request.method == "POST" and request.POST.get("action") == "creer_espace":
            # Configuration rapide : crée (si besoin) un établissement pour
            # l'enseignant, puis un parcours et un espace de cours, le tout
            # directement depuis la plateforme (sans passer par /admin/).
            etablissement = request.user.etablissement
            if etablissement is None:
                nom_etablissement = request.POST.get("nom_etablissement", "").strip() or "Mon établissement"
                etablissement = Etablissement.objects.create(nom=nom_etablissement, localite="")
                request.user.etablissement = etablissement
                request.user.save(update_fields=["etablissement"])

            intitule_parcours = request.POST.get("intitule_parcours", "").strip()
            nom_espace = request.POST.get("nom_espace", "").strip()

            if intitule_parcours and nom_espace:
                parcours = Parcours.objects.create(etablissement=etablissement, intitule=intitule_parcours)
                Espace.objects.create(parcours=parcours, nom=nom_espace)

            return redirect("mes_ressources")

        if request.method == "POST" and request.POST.get("action") == "ajouter_ressource":
            titre = request.POST.get("titre", "").strip()
            espace = espaces.filter(id_espace=request.POST.get("espace")).first()
            niveau = request.POST.get("niveau_requis", Ressource.NIVEAU_MOYEN)
            fichier = request.FILES.get("fichier")

            if titre and espace:
                ressource = Ressource.objects.create(
                    espace=espace,
                    enseignant=profil,
                    titre=titre,
                    type_ressource=Ressource.TYPE_DOCUMENT,
                    niveau_requis=niveau,
                )
                document = Document.objects.create(ressource=ressource, fichier=fichier or "")

                if fichier:
                    from . import ia_service
                    try:
                        ia_service.indexer_document(document)
                    except ia_service.ErreurServiceIA:
                        # L'indexation échoue silencieusement si Ollama n'est pas
                        # joignable : la ressource reste publiée, juste pas encore
                        # utilisable par l'assistant IA (document.indexe = False).
                        pass

                return redirect("mes_ressources")

        if request.method == "POST" and request.POST.get("action") == "ajouter_quiz":
            titre = request.POST.get("titre_quiz", "").strip()
            espace = espaces.filter(id_espace=request.POST.get("espace_quiz")).first()
            niveau = request.POST.get("niveau_requis_quiz", Ressource.NIVEAU_MOYEN)
            duree = request.POST.get("duree_minutes", "10")

            # Nombre de questions dynamique (le prof peut en ajouter autant
            # qu'il veut via le bouton "+ Ajouter une question" en JS) : on
            # parcourt les champs tant qu'ils existent, avec un plafond de
            # sécurité à 100 questions.
            questions_valides = []
            i = 1
            while f"question_{i}" in request.POST and i <= 100:
                enonce = request.POST.get(f"question_{i}", "").strip()
                if enonce:
                    choix_textes = [
                        request.POST.get(f"choix_{i}_{j}", "").strip() for j in range(4)
                    ]
                    index_correct = request.POST.get(f"correct_{i}")
                    if all(choix_textes) and index_correct is not None:
                        questions_valides.append((enonce, choix_textes, int(index_correct)))
                i += 1

            if titre and espace and questions_valides:
                ressource = Ressource.objects.create(
                    espace=espace,
                    enseignant=profil,
                    titre=titre,
                    type_ressource=Ressource.TYPE_QUIZ,
                    niveau_requis=niveau,
                )
                quiz = Quiz.objects.create(
                    ressource=ressource,
                    nombre_questions=len(questions_valides),
                    duree_minutes=int(duree) if duree.isdigit() else 10,
                )
                for ordre, (enonce, choix_textes, index_correct) in enumerate(questions_valides):
                    question = Question.objects.create(quiz=quiz, enonce=enonce, ordre=ordre)
                    for j, texte_choix in enumerate(choix_textes):
                        Choix.objects.create(
                            question=question, texte=texte_choix, est_correct=(j == index_correct),
                        )

                return redirect("mes_ressources")

        contexte = {
            "ressources": profil.ressources_publiees.select_related("espace").order_by("-date_ajout"),
            "espaces": espaces,
            "niveaux": Ressource.NIVEAU_CHOICES,
            "a_etablissement": request.user.etablissement is not None,
        }
        return render(request, "mes_ressources_enseignant.html", contexte)

    elif request.user.role == Utilisateur.ROLE_APPRENANT:
        profil = request.user.profil_apprenant
        contexte = {
            "ressources": Ressource.objects.filter(
                espace__parcours__inscriptions__apprenant=profil
            ).select_related("espace").distinct().order_by("-date_ajout"),
        }
        return render(request, "mes_ressources_apprenant.html", contexte)

    return redirect("accueil")


@exige_role(Utilisateur.ROLE_ENSEIGNANT)
def modifier_ressource(request, id_ressource):
    """
    Permet à l'enseignant propriétaire de modifier le titre, l'espace
    et le niveau requis d'une ressource déjà publiée.
    """
    from .models import Espace, Ressource

    profil = request.user.profil_enseignant
    ressource = Ressource.objects.filter(id_ressource=id_ressource, enseignant=profil).first()
    if ressource is None:
        return redirect("mes_ressources")

    espaces = Espace.objects.filter(parcours__etablissement=request.user.etablissement)

    if request.method == "POST":
        titre = request.POST.get("titre", "").strip()
        espace = espaces.filter(id_espace=request.POST.get("espace")).first()
        niveau = request.POST.get("niveau_requis", Ressource.NIVEAU_MOYEN)

        if titre and espace:
            ressource.titre = titre
            ressource.espace = espace
            ressource.niveau_requis = niveau
            ressource.save(update_fields=["titre", "espace", "niveau_requis"])
            return redirect("mes_ressources")

    return render(request, "modifier_ressource.html", {
        "ressource": ressource,
        "espaces": espaces,
        "niveaux": Ressource.NIVEAU_CHOICES,
    })

@exige_role(Utilisateur.ROLE_ENSEIGNANT)
def supprimer_ressource(request, id_ressource):
    """
    Supprime une ressource appartenant à l'enseignant connecté (et, par
    cascade Django, son Document/Vidéo/Quiz associé).
    """
    from .models import Ressource

    profil = request.user.profil_enseignant
    ressource = Ressource.objects.filter(id_ressource=id_ressource, enseignant=profil).first()

    if request.method == "POST" and ressource is not None:
        ressource.delete()

    return redirect("mes_ressources")


@login_required
def parcours_disponibles(request):
    """
    Liste des parcours de l'établissement de l'apprenant, avec un bouton
    pour s'y inscrire (crée une Inscription). Sans inscription à un
    parcours, un apprenant ne voit aucune ressource ni quiz.
    """
    from .models import Inscription, Parcours

    if request.user.role != Utilisateur.ROLE_APPRENANT:
        return redirect("accueil")

    profil = request.user.profil_apprenant

    if request.method == "POST":
        parcours_id = request.POST.get("parcours")
        parcours = Parcours.objects.filter(
            id_parcours=parcours_id, etablissement=request.user.etablissement
        ).first()
        if parcours:
            Inscription.objects.get_or_create(apprenant=profil, parcours=parcours)
        return redirect("parcours_disponibles")

    deja_inscrit = profil.inscriptions.values_list("parcours_id", flat=True)
    contexte = {
        "parcours_disponibles": Parcours.objects.filter(
            etablissement=request.user.etablissement
        ).exclude(id_parcours__in=deja_inscrit),
        "mes_parcours": profil.inscriptions.select_related("parcours"),
    }
    return render(request, "parcours_disponibles.html", contexte)


@login_required
def passer_quiz(request, id_ressource):
    """
    Affiche les questions d'un quiz (GET) et corrige les réponses
    soumises (POST) : calcule la note sur 20 et crée l'Evaluation
    correspondante — ce qui déclenche automatiquement (via signals.py)
    le reclassement K-means et la génération de recommandations.
    """
    from .models import Evaluation, Ressource

    if request.user.role != Utilisateur.ROLE_APPRENANT:
        return redirect("accueil")

    profil = request.user.profil_apprenant
    ressource = Ressource.objects.filter(
        id_ressource=id_ressource, type_ressource=Ressource.TYPE_QUIZ
    ).first()

    if ressource is None or not hasattr(ressource, "quiz"):
        return redirect("mes_ressources")

    quiz = ressource.quiz
    questions = quiz.questions.prefetch_related("choix")

    if request.method == "POST":
        nombre_questions = questions.count()
        nombre_correctes = 0

        for question in questions:
            choix_soumis = request.POST.get(f"question_{question.id_question}")
            if choix_soumis and question.choix.filter(id_choix=choix_soumis, est_correct=True).exists():
                nombre_correctes += 1

        note = round((nombre_correctes / nombre_questions) * 20, 2) if nombre_questions else 0

        evaluation = Evaluation.objects.create(apprenant=profil, quiz=quiz, note=note)

        return render(request, "quiz_resultat.html", {
            "ressource": ressource,
            "note": evaluation.note,
            "nombre_correctes": nombre_correctes,
            "nombre_questions": nombre_questions,
        })

    return render(request, "quiz_passer.html", {"ressource": ressource, "quiz": quiz, "questions": questions})


@exige_role(Utilisateur.ROLE_APPRENANT)
def tableau_bord_apprenant(request):
    from .models import Ressource, Statistiques

    profil = request.user.profil_apprenant
    statistiques, _ = Statistiques.objects.get_or_create(apprenant=profil)

    contexte = {
        "statistiques": statistiques,
        "inscriptions": profil.inscriptions.select_related("parcours"),
        "recommandations": profil.recommandations.select_related("ressource")[:5],
        "nombre_ressources_disponibles": Ressource.objects.filter(
            espace__parcours__inscriptions__apprenant=profil
        ).distinct().count(),
        "pourcentage_progression": min(int(statistiques.moyenne_generale * 5), 100) if statistiques.moyenne_generale else 10,
    }
    return render(request, "tableau_bord_apprenant.html", contexte)


@login_required
def changer_mot_de_passe(request):
    """
    Permet à n'importe quel utilisateur connecté (admin, enseignant,
    apprenant) de changer son mot de passe. Il doit connaître son mot de
    passe actuel — ça évite qu'une session laissée ouverte sur un poste
    permette à quelqu'un d'autre de voler le compte en changeant le mot
    de passe à sa place.
    """
    from django.contrib import messages
    from django.contrib.auth import update_session_auth_hash

    erreur = None

    if request.method == "POST":
        ancien = request.POST.get("ancien_mot_de_passe", "")
        nouveau = request.POST.get("nouveau_mot_de_passe", "")
        confirmation = request.POST.get("confirmation_mot_de_passe", "")

        if not request.user.check_password(ancien):
            erreur = "Mot de passe actuel incorrect."
        elif len(nouveau) < 4:
            erreur = "Le nouveau mot de passe doit faire au moins 4 caractères."
        elif nouveau != confirmation:
            erreur = "Les deux mots de passe ne correspondent pas."
        else:
            request.user.set_password(nouveau)
            request.user.save(update_fields=["password"])
            # Sans ça, Django considérerait la session actuelle comme
            # invalide après le changement de mot de passe, et
            # déconnecterait l'utilisateur immédiatement.
            update_session_auth_hash(request, request.user)
            messages.success(request, "Mot de passe changé avec succès.")
            return redirect("changer_mot_de_passe")

    return render(request, "changer_mot_de_passe.html", {"erreur": erreur})
