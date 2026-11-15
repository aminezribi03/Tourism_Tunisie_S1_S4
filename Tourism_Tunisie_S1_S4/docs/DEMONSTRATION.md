# Une demonstration en cinq minutes

1. **Le besoin.** Dire : « Nous voulons comprendre l'evolution du tourisme tunisien et preparer
   la prevision des recettes. Les informations etaient reparties entre plusieurs fichiers. »
2. **L'ETL.** Lancer `python -m tourism.etl`. Montrer le statut OK et le fichier `controles.csv`.
   Expliquer qu'un total est utilise pour verifier le detail, jamais pour l'additionner une seconde fois.
3. **La base.** Montrer `outputs/tourisme.sqlite` et `docs/DWH.md`. Dire : « Les dimensions
   repondent a quand, ou et quel marche. Les faits contiennent les nombres a analyser. »
4. **L'interface.** Ouvrir localhost:8501. Choisir 2023. Montrer les 6 920,6 MDT, puis 2019 pour
   expliquer pourquoi les arrivees detaillees deviennent indisponibles.
5. **Les interactions.** Dans Hebergement, selectionner SOUSSE : les lits et les tableaux changent.
   Dans Recettes, passer en MEUR et expliquer la conversion mensuelle indicative.
6. **Power BI.** Ouvrir le PBIP, Actualiser, selectionner 2023 et montrer un segment. Verifier
   ces etapes au moins une fois sur Windows avant la presentation.
7. **La qualite.** Montrer la valeur 109,8 % dans l'audit. Elle est conservee dans les sources,
   mais le taux nettoye est vide en attente de verification. Ne pas presenter toutes les exclusions
   d'audit comme des erreurs : beaucoup sont des totaux normaux.
8. **La suite.** Ouvrir Previsions. Dire : « L'espace est reserve. En semaine 5, nous comparerons
   deux familles de modeles sur une periode de test gardee a part. »

## Reponses simples aux questions du professeur

**Pourquoi deux sources ?** L'ONTT decrit le tourisme. La BCT donne le contexte du change.
Elles viennent de deux organismes et sont rapprochees sur les memes mois.

**Pourquoi SQLite ?** La base est un fichier. Elle s'installe facilement chez un autre membre
du groupe et conserve les relations et contraintes utiles au projet.

**Pourquoi plusieurs faits ?** Une recette est mensuelle et nationale. Une capacite est annuelle,
regionale et par categorie. Les melanger dans une seule table provoquerait des repetitions.

**Que fait Python ?** Il lit, nettoie, controle, charge et prepare les donnees pour les graphiques.

**L'IA est ou ?** Elle appartient a la semaine 5. La cible, la table et l'ecran sont prepares,
mais aucun resultat n'est invente.

**Qu'est-ce qui reste a faire avant le depot ?** Confirmer la collecte originale ONTT et ses
metadonnees, faire valider le schema par les encadrants, ouvrir et verifier le PBIP sur Windows,
et configurer l'integration securisee Power BI si cette integration en ligne est demandee.
