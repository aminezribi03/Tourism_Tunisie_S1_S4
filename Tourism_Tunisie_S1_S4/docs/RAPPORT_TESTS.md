# Rapport de verification

Verification realisee le 15 novembre 2026, sous Linux, avec Python 3.12.14.

- Installation dans un environnement virtuel neuf, sans reutiliser les bibliotheques globales.
- Installation de `requirements-dev.txt`, incluant les dependances de l'application.
- `pip check` : aucune dependance cassee.
- `pytest` : **27 tests reussis, 0 echec**. Resultat detaille dans `outputs/tests_execution.txt`
  et `outputs/tests_junit.xml`.
- ETL execute sur les fichiers fournis : **20 controles reussis**.
- Compilation des modules et des scripts Python sans erreur de syntaxe.
- Demarrage reel de Streamlit dans l'environnement neuf : reponse HTTP du point de sante = `ok`.
- Guide PDF genere, neuf pages rendues et inspectees ; aucune page vide ni texte coupe observe.

| Domaine | Verification |
|---|---|
| BCT | 96 mois, 192 taux, virgules decimales et comparaison avec le classeur converti |
| Nettoyage | Noms harmonises, manquants distincts de zero, taux 109,8 % isole |
| DWH | Cles etrangeres, unicite du grain, tracabilite, presence des mois |
| Totaux | Recettes, arrivees, nuitees, lits, etablissements et investissements compares aux references |
| Robustesse | Doublon rejete, mauvaise source rejetee, base precedente preservee, reconstruction sans cumul |
| Interface | Huit pages executees par AppTest, filtres annee/region/devise, selection vide et previsions absentes |
| Power BI | Schemas officiels PBIP/PBIR/PBISM, references de colonnes/mesures et relations |
| Portabilite | ZIP extrait dans un dossier avec espaces, ETL et generateur relances, 27 tests reussis sur cette copie |

Les schemas Microsoft inclus dans `tests/schemas/` permettent de refaire la validation hors ligne.
Leur URL d'origine figure dans `tests/schemas/index.json`. Ils ne constituent pas un moteur DAX.

## Verifications qui restent sur le PC destinataire

Les fichiers BAT et Power BI Desktop n'ont pas ete executes sous Windows. Il faut ouvrir le PBIP,
Actualiser, verifier les chiffres de controle et les interactions, puis sauvegarder le rapport.
L'integration du rapport Microsoft dans l'interface attend l'URL securisee du rapport publie.
AppTest controle les elements et interactions Streamlit ; ce n'est pas une verification visuelle
complete de chaque page dans un navigateur Windows.

Les controles techniques ne remplacent pas la validation de conception par les encadrants ni
la confirmation de la collecte originale ONTT, de sa date d'extraction et de sa licence.
