# Fiche de collecte et provenance

Les fichiers ont ete fournis dans la conversation du 15 novembre 2026. Cette date est la date
de reception, **pas** la date d'extraction originale. Les organismes et les liens ci-dessous sont
identifies a partir des metadonnees des classeurs et des pages officielles consultees le meme jour.

## Source principale tourisme : ONTT

- Organisme : Office National du Tourisme Tunisien.
- Document indique : *Tourisme tunisien en chiffres - Extrait 2023*.
- URL officielle consultee : https://www.ontt.tn/sites/default/files/inline-files/EXTRAIT%202023%20.pdf
- Fichier utilise pour l'ETL : `data/raw/pwer bi base de donnes.xlsx`.
- Methode : transcription/structuration deja fournie en Excel. Le code importe les feuilles et les nettoie.
- PDF source original : non joint. Les tentatives de telechargement local ont retourne HTTP 503.
  Le document et les chiffres de synthese sont consultables par recherche web officielle.
- Extraction originale : **non fournie, a completer avec le groupe**.
- Licence ou autorisation de reutilisation : **non fournie, a verifier**. Aucune licence ouverte n'est inventee.
- Periodes : recettes mensuelles 2016-2023, arrivees/nuitees/saisons 2021-2023,
  sites/musees 2019-2023, offre/investissements/restaurants : instantanes 2023.
- Volume du classeur : 18 feuilles, dont 96 recettes mensuelles, 207 lignes d'arrivees,
  174 de nuitees, 285 de capacite et 342 d'occupation avant nettoyage.
- Qualite : sous-totaux et % melanges aux comptes, variantes de noms, cellules vides,
  un taux de 109,8 %, deux blocs de duree regionale sans leur libelle de population.

Le cahier des charges demande une vraie collecte, et rejette une base deja nettoyee comme source
principale autonome. Ce paquet n'invente pas une nouvelle collecte du PDF : il exploite la
transcription fournie et documente la limite. Le groupe doit conserver le PDF brut et la trace
de son extraction avant le depot. La provenance officielle de la serie est documentee.

## Source independante de change : BCT

- Organisme : Banque Centrale de Tunisie.
- Tableau : *Moyennes des cours du marche interbancaire (mensuel)*.
- URL officielle : https://www.bct.gov.tn/bct/siteprod/tableau_statistique.jsp?params=PL213010
- Fichier utilise : `data/raw/BCT_statistque.xls`.
- Format reel : **HTML imbrique**, bien que l'extension soit `.xls`.
- Methode d'origine indiquee : export du site BCT. L'ETL parse directement les cellules HTML.
- Extraction originale et licence : **non fournies, a confirmer**.
- Periode : janvier 2016-decembre 2023, 96 mois, deux devises, 192 valeurs.
- Unite : TND pour 1 EUR ou 1 USD. Exemple janvier 2016 : EUR = 2,2193 TND ; USD = 2,0445 TND.
- Qualite : pas de mois manquant. Les virgules decimales sont converties explicitement.
- Controle : comparaison des 192 taux bruts au fichier BCT converti fourni.

Les sources sont independantes par organisme et contenu. L'integration technique combine
Excel structure et HTML brut, puis rapproche les deux series par mois.

## Role des autres fichiers

| Fichier | Role | Traitement |
|---|---|---|
| Source2_BCT_change.xlsx | Copie BCT convertie et fiche de collecte | Controle du HTML, pas de cumul |
| Base_Maitresse_Tourisme_Tunisie.xlsx | Empilement de donnees touristiques derivees | Inventorie et conserve ; pas de rechargement en double |
| Echantillon_donnees_Tourisme_Tunisie.xlsx | Echantillons de tables et 96 mois de recettes | Controle des recettes, exemples pour S1 |
| Projet_integre_3LBC_BI_2026-2027 (1).pdf | Cahier des charges | Perimetre et correspondance des livrables |

L'inventaire exhaustif des feuilles, volumes, cellules vides et doublons est genere dans
`outputs/inventaire_sources.json`. Les empreintes SHA-256 sont dans `outputs/fichiers_sha256.csv`.
Le dictionnaire des donnees brutes et du DWH est dans `docs/DICTIONNAIRE_DONNEES.csv`.
