# Correspondance avec le cahier des charges

| Semaine | Demande | Fichier ou fonction livre | Etat |
|---|---|---|---|
| 1 | Probleme metier, acteurs et KPI | FICHE_PROJET.md | Redige |
| 1 | Fiche de collecte et dictionnaire | FICHE_COLLECTE.md, DICTIONNAIRE_DONNEES.csv | Fourni ; date d'extraction et licence originales a confirmer |
| 1 | Deux sources heterogenes et historique | Excel ONTT derive + HTML BCT, serie de 96 mois | Integre ; PDF ONTT brut a conserver par le groupe |
| 1 | Echantillon et schema preliminaire | Echantillon fourni dans data/raw, DWH.md | Fourni |
| 2 | Conception validee | DWH.md et outputs/schema.sql | Conception fournie ; validation encadrant a obtenir |
| 2 | Premiers jobs ETL | tourism/etl.py, cleaning.py | Execute et teste |
| 3 | Qualite, coherence des volumes, tracabilite | rapport_qualite.json, controles.csv, audit_lignes.csv | Execute ; voir rapport de tests |
| 3 | DWH alimente | outputs/tourisme.sqlite | Fourni et regenerable |
| 3 | Power BI, DAX, segments, exploration | powerbi/Tourisme_Tunisie.pbip et cinq pages PBIR | Definitions controlees ; ouverture/rendu/DAX a verifier sur Windows |
| 4 | Interface conviviale et interactive | app.py, Streamlit | Pages et filtres testes |
| 4 | Integration des tableaux de bord | Graphiques locaux operationnels + page d'integration Power BI | Local operationnel ; rapport Microsoft integre apres publication/URL du groupe |
| 4 | Espace previsions | Ecran Previsions et table fact_previsions | Fourni, vide |

Les modeles statistiques et d'apprentissage, les tests ADF/KPSS et les metriques de prevision
relèvent de la semaine 5. Le rapport final de 10 a 15 pages et la soutenance relevent de la semaine 6.
Le guide PDF fourni explique l'etat S1-S4 ; il ne pretend pas etre le rapport final S6.
