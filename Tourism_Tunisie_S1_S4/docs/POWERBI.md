# Utiliser le projet Power BI

## Ouverture

1. Utiliser un PC Windows avec Power BI Desktop installe : https://www.microsoft.com/power-platform/products/power-bi/desktop
2. Extraire tout le ZIP et executer `INSTALLER_WINDOWS.bat`.
3. Ouvrir `powerbi/Tourisme_Tunisie.pbip`.
4. Si Desktop le demande, activer la prise en charge des projets PBIP dans les options de fonctionnalites en preversion, puis redemarrer Desktop.
5. Cliquer sur **Actualiser** pour importer les CSV dans le modele.
6. Sur la page Recettes, selectionner 2023 dans le segment Annee.

Valeurs de controle : recettes 6 920,6 MDT ; variation sur 2022 environ 27,7 % ;
arrivees 9 370 511 ; nuitees 25 351 033 ; lits 230 726 ; etablissements 905.

L'absence de cache de donnees dans un projet PBIP est normale. L'import se fait au premier
rafraichissement. Aucun compte Power BI n'est necessaire pour les pages Streamlit locales.

## Contenu

- Cinq pages : recettes/change, marches/saisons, hebergement, territoires et espace S5.
- Modele dimensionnel importe depuis les CSV du DWH ; relations a sens unique.
- 17 mesures DAX dans `fact_recettes`, dossier KPI.
- Segments par annee, marche, region et categorie, selon la page.
- Exploration region puis categorie dans le graphique des lits.
- Les mesures de taux ne font pas de somme de pourcentages.
- La mesure de variation annuelle attend une seule annee selectionnee. Sans cela elle reste vide.
- La page previsions reste vide en semaine 4.

Les tables de references sont masquees pour limiter les sommes accidentelles. Les clefs
techniques sont masquees. Le calendrier mensuel comporte une hierarchie Annee/Trimestre/Mois.

## Actualiser apres un changement

Fermer Desktop avant la generation : le programme regenere les definitions du modele et du
rapport. Sauvegarder ailleurs vos personnalisations avant de le relancer.

```powershell
.venv\Scripts\python.exe -m tourism.etl
.venv\Scripts\python.exe scripts\configure_powerbi.py
```

Rouvrir le PBIP et Actualiser. Si seul le contenu des CSV a change et que le modele ne change
pas, il suffit de relancer l'ETL et d'actualiser Desktop. Si le dossier est deplace, regenerer
le chemin avec `configure_powerbi.py` ou modifier le parametre Power Query `RootPath`.

## Verification restante sous Windows

Le code et les fichiers ont ete controles sous Linux. Les fichiers PBIR sont valides selon les
schemas publics Microsoft fournis dans les tests. Ces controles ne remplacent pas l'ouverture
native ni l'evaluation DAX. A effectuer sur le PC destinataire :

- Ouverture sans message d'erreur.
- Actualisation des 27 tables.
- Verification des valeurs de controle ci-dessus.
- Clic sur les segments et exploration du graphique des lits.
- Sauvegarde eventuelle en PBIX pour le depot si les encadrants le demandent.

Si une version de Desktop ne prend pas en charge le projet, la solution de repli est :
**Obtenir des donnees > Texte/CSV**, importer les fichiers `outputs/powerbi_csv/dim_*.csv`,
`fact_*.csv` et `ref_controles_source.csv`, recreer les relations de `outputs/schema.sql`,
puis ajouter les mesures de `powerbi/mesures.dax` une par une. Ne pas importer les vues
`vw_*.csv` en plus des faits pour calculer les memes totaux.

## Integration dans l'interface

La partie locale affiche deja les graphiques issus du DWH. Pour integrer le rapport Microsoft
dans l'onglet Power BI, publier le rapport dans **votre** espace Power BI puis recuperer l'URL
d'integration securisee. Creer `config.local.json` a la racine :

```json
{"powerbi_embed_url": "https://app.powerbi.com/reportEmbed?reportId=VOTRE_ID&groupId=VOTRE_ESPACE"}
```

L'utilisateur doit avoir les droits et, selon le cas, la licence Power BI necessaire.
Le code ne publie aucun rapport, ne cree aucun compte et ne contient aucun mot de passe.
Les filtres Streamlit et ceux du rapport Microsoft sont independants.

Documentation Microsoft consultee le 15/11/2026 :

- https://learn.microsoft.com/power-bi/developer/projects/projects-report
- https://learn.microsoft.com/power-bi/developer/projects/projects-dataset
- https://learn.microsoft.com/power-bi/developer/embedded/projects-enhanced-report-format
- Exemple Microsoft pour la version de contenu PBIR : https://github.com/microsoft/BCApps/blob/main/src/Apps/W1/PowerBIReports/Power%20BI%20Files/Projects%20app/Projects%20app.Report/definition/version.json
