---
titre: Probabilités conditionnelles et formule des probabilités totales
matiere: Mathématiques
niveau: Lycée (Terminale)
source: https://senprof2.education.sn/Élèves/4.Secondaire/3.Terminale/SenSpatial/activities/Probabilites.html
origine: Bibliothèque numérique nationale du MEN (Sénégal) — plateforme SENKALA
---

# Probabilités conditionnelles et formule des probabilités totales

## Probabilité conditionnelle

p(B|A) se lit "probabilité de B sachant A" : c'est la probabilité que l'événement B se réalise, sachant que l'événement A s'est déjà réalisé.

## La formule des probabilités totales

Si les événements A₁, A₂, ..., Aₙ forment une partition de l'univers (ils sont disjoints et couvrent tous les cas possibles), alors pour un événement B :

**p(B) = p(A₁) × p(B|A₁) + p(A₂) × p(B|A₂) + ... + p(Aₙ) × p(B|Aₙ)**

## Exemple concret : classification d'hôtels à Dakar

En 2023, les hôtels de Dakar se répartissent en trois catégories : 25 % en catégorie A, 25 % en catégorie B, 50 % en catégorie C.

Chaque année, certains hôtels changent de catégorie : par exemple, 5 % des hôtels de catégorie A rétrogradent en B (donc 94 % restent en A, une fois qu'on tient compte des autres transitions possibles), et 20 % des hôtels de catégorie B sont promus en A.

## Calcul de la probabilité pour 2024

Pour calculer la probabilité qu'un hôtel soit en catégorie A en 2024, on additionne toutes les façons d'y arriver :

p(A en 2024) = p(A en 2023) × p(reste en A) + p(B en 2023) × p(passe de B à A) + p(C en 2023) × p(passe de C à A)

En appliquant cette méthode aux trois catégories, on obtient pour 2024 : environ 29 % en catégorie A, 30 % en catégorie B, 41 % en catégorie C.

## À retenir

La formule des probabilités totales permet de calculer la probabilité globale d'un événement en décomposant tous les chemins possibles qui peuvent y mener, chacun pondéré par sa propre probabilité.
