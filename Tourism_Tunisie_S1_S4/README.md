# Tourisme Tunisie - projet integre BI, semaines 1 a 4

Une application locale pour analyser les recettes touristiques, les marches,
l'hebergement, les investissements et les sites tunisiens a partir des fichiers fournis.

## Demarrage sur Windows

1. Extraire **tout** le ZIP dans un dossier, par exemple `Documents\Tourism_Tunisie_S1_S4`.
2. Installer **Python 3.12 64 bits** depuis https://www.python.org/downloads/ et cocher **Add Python to PATH**.
3. Double-cliquer sur **INSTALLER_WINDOWS.bat**. Internet est necessaire pour installer les bibliotheques.
4. Une fois l'installation terminee, double-cliquer sur **LANCER_WINDOWS.bat**.
5. Ouvrir http://localhost:8501 si le navigateur ne s'ouvre pas automatiquement.

Garder la fenetre de commande ouverte pendant l'utilisation. `Ctrl+C` arrete l'application.
L'application fonctionne ensuite localement avec les fichiers inclus, sans cle API.
La premiere installation peut prendre plusieurs minutes.

**For your friend:** unzip the whole folder, install Python 3.12, run
`INSTALLER_WINDOWS.bat`, then `LANCER_WINDOWS.bat`. Open http://localhost:8501.

## Ce qui est inclus

- Les six fichiers fournis, conserves dans `data/raw/` sans modification.
- Un ETL Python relancable et une base SQLite deja alimentee.
- Les exports CSV des dimensions, des faits et des vues pour Power BI.
- Un projet Power BI **PBIP/PBIR** : cinq pages, relations et mesures DAX.
- Une interface Streamlit avec filtres, graphiques, exploration et telechargements CSV.
- Un espace previsions vide pour la semaine 5.
- Des tests automatises, les controles de qualite et un guide PDF en francais simple.

## Power BI

Apres l'installation, ouvrir `powerbi/Tourisme_Tunisie.pbip` dans **Power BI Desktop sous Windows**,
puis cliquer sur **Actualiser**. Le programme d'installation configure le chemin des CSV pour ce PC.
Si vous deplacez le dossier, fermez Power BI puis relancez :

```powershell
.venv\Scripts\python.exe scripts\configure_powerbi.py
```

Le projet est fourni au format source PBIP, pas PBIX. Les definitions JSON et leurs references sont
controlees automatiquement. **L'ouverture, le calcul DAX et le rendu natif Power BI Desktop n'ont pas
pu etre executes dans l'environnement Linux de preparation.** Ils doivent etre verifies sous Windows.
Voir `docs/POWERBI.md` pour les etapes et la solution de repli par import CSV.

La page Power BI de l'interface propose un emplacement d'integration securisee. Pour y afficher le
rapport Microsoft, il faut d'abord le publier dans votre propre espace Power BI et ajouter son URL
dans `config.local.json`. L'application locale et ses graphiques fonctionnent deja sans cette etape.

## Commandes manuelles

Depuis le dossier extrait, apres creation de l'environnement :

```powershell
.venv\Scripts\python.exe -m tourism.etl
.venv\Scripts\python.exe scripts\configure_powerbi.py
.venv\Scripts\python.exe -m streamlit run app.py
```

Sur macOS/Linux avec Python 3.12 :

```bash
bash installer_mac_linux.sh
bash lancer_mac_linux.sh
```

Power BI Desktop s'utilise sur Windows. L'interface locale fonctionne aussi sur macOS/Linux.

## Verification

Sous Windows, ouvrir `TESTER_WINDOWS.bat`. Ou :

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
```

Le dossier `outputs/` contient la base, les controles ETL, l'audit des lignes et les fichiers Power BI.
Les tests construisent aussi une base temporaire et verifient les filtres de l'interface.

## Points a presenter clairement

- La serie mensuelle contient **96 mois observes**, de janvier 2016 a decembre 2023.
- Les fichiers maitresse, echantillon et BCT converti sont des copies derivees ou de controle.
  Ils ne sont pas additionnes comme de nouvelles observations.
- Les totaux et les pourcentages sont separes des details.
- Une valeur manquante reste manquante. Un taux source de 109,8 % est isole pour verification.
- La feuille `Duree_Region` contient deux blocs sans libelle de population : elle reste dans les
  fichiers bruts et dans l'audit, sans indicateur calcule a partir de ces lignes.
- Capacite, occupation, investissements et restaurants sont des instantanes du rapport **2023**.
- Le PDF ONTT original n'etait pas joint : la partie tourisme utilise la transcription Excel fournie.
  Son URL officielle est documentee. Conserver le PDF original et completer la date d'extraction
  et la licence avec le groupe avant le depot. Ne pas presenter les Excel derives comme une collecte brute autonome.
- Le developpement livre s'arrete a la **semaine 4**. Les modeles IA et leur evaluation appartiennent
  a la semaine 5 et ne sont pas simules.
- La validation de la conception par les encadrants reste une action du groupe.

Lire d'abord `docs/Guide_Projet_Tourisme_S1_S4.pdf`, puis `docs/DEMONSTRATION.md`.
