import os
import django

# Configuration de l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plateforme_edu.settings')
django.setup()

from plateforme_edu.ia_service import collection, _convertir_en_chiffres, lire_et_enregistrer_pdf

def gerer_ingestion_interactive():
    """Permet d'ajouter un nouveau cours à la base à chaque lancement si l'utilisateur le souhaite."""
    nb_docs = collection.count()
    print(f"\n📊 Nombre actuel de segments (chunks) dans ChromaDB : {nb_docs}")

    while True:
        reponse = input("\n👉 Souhaites-tu ajouter un nouveau PDF de cours avant de tester ? (o/n) : ").strip().lower()
        if reponse in ['o', 'oui']:
            chemin_pdf = input("📁 Entrez le nom/chemin du fichier PDF dans app/ (ex: Reseau.pdf) : ").strip()
            if os.path.exists(chemin_pdf):
                print("⏳ Indexation du PDF en cours via Ollama...")
                # On passe un ID simple (ex: 2) pour éviter le doublon "doc_doc_..."
                id_doc = nb_docs + 1
                succes = lire_et_enregistrer_pdf(id_document=id_doc, chemin_pdf=chemin_pdf)
                if succes:
                    print(f"✅ PDF indexé avec succès ! Nouveau total : {collection.count()} segments.")
                else:
                    print("❌ Échec de l'indexation du PDF.")
            else:
                print(f"❌ Fichier introuvable à l'emplacement : {chemin_pdf}")
        elif reponse in ['n', 'non']:
            break
        else:
            print("Veuillez répondre par 'o' (oui) ou 'n' (non).")

def tester_distances():
    gerer_ingestion_interactive()

    if collection.count() == 0:
        print("\n⚠️ La base est vide. Aucun test de distance ne peut être effectué.")
        return

    questions_test = [
        # 🟢 Questions PERTINENTES
        ("Qu'est-ce qu'une base de données relationnelle ?", "PERTINENT"),
        ("Explique le principe du RAG en informatique", "PERTINENT"),
        
        # 🟡 Questions ZONE GRISE / Culture Générale
        ("Qui est le président de la République ?", "ZONE GRISE"),
        ("Comment vas-tu aujourd'hui ?", "SMALL TALK"),
        
        # 🔴 Questions HORS-SUJET ABSOLU
        ("Comment préparer une omelette aux champignons ?", "HORS-SUJET")
    ]

    print("\n=================== TEST DE CALIBRAGE DES DISTANCES (COSINUS) ===================")
    for q, categorie in questions_test:
        vecteur = _convertir_en_chiffres(q)
        if not vecteur:
            print(f"❌ Erreur de vectorisation pour : '{q}'")
            continue

        res = collection.query(query_embeddings=[vecteur], n_results=1)
        
        if res and res.get("documents") and res["documents"][0] and res.get("distances"):
            dist = res["distances"][0][0]
            doc_extrait = res["documents"][0][0][:70].replace("\n", " ")
            print(f"\n[Catégorie: {categorie}]")
            print(f"❓ Question : '{q}'")
            print(f"📏 Distance Cosinus : {dist:.4f}")
            print(f"📄 Extrait trouvé  : '{doc_extrait}...'")
        else:
            print(f"\n❓ Question : '{q}' -> Aucun document trouvé dans ChromaDB.")
            
    print("\n=================================================================================\n")

if __name__ == "__main__":
    tester_distances()
