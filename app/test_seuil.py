import os
import django

# Configuration de l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plateforme_edu.settings')
django.setup()

from plateforme_edu.ia_service import collection, _convertir_en_chiffres, lire_et_enregistrer_pdf

def preparer_base_de_test():
    """Vérifie si la collection contient des documents, sinon demande d'en charger un."""
    nb_docs = collection.count()
    print(f"📊 Nombre de segments (chunks) dans 'cours_universite_v2' : {nb_docs}")
    
    if nb_docs == 0:
        print("\n⚠️ La collection est vide (normale après renommage).")
        chemin_pdf = input("👉 Entrez le chemin d'un fichier PDF de cours de test (ex: media/mon_cours.pdf) : ").strip()
        if os.path.exists(chemin_pdf):
            print("⏳ Indexation du PDF en cours...")
            succes = lire_et_enregistrer_pdf(id_document=1, chemin_pdf=chemin_pdf)
            if succes:
                print("✅ PDF indexé avec succès !")
            else:
                print("❌ Échec de l'indexation du PDF.")
        else:
            print(f"❌ Fichier introuvable : {chemin_pdf}. Les tests de distance risquent de ne rien renvoyer.")

def tester_distances():
    preparer_base_de_test()

    questions_test = [
        # 🟢 Questions PERTINENTES (doivent correspondre directement au cours indexé)
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
            print(f"❌ Erreur de vectorisation (Ollama indisponible ?) pour : '{q}'")
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