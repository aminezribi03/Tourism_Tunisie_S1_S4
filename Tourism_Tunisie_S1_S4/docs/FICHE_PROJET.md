# Fiche projet

**Domaine :** tourisme tunisien. **Niveau :** 3LBC BI. **Perimetre :** semaines 1 a 4.

**Problematique :** comment suivre la reprise du tourisme tunisien, identifier les marches et
territoires importants, et preparer la prevision des recettes mensuelles ?

Les acteurs envisages sont les responsables du tourisme, les analystes et les responsables
de l'offre touristique. Leurs decisions portent sur les campagnes par marche, les periodes de
forte demande et les besoins d'investissement. Ce sont des usages proposes, sans entretien metier invente.

| Question | KPI | Formule | Grain et suivi |
|---|---|---|---|
| Combien rapporte le tourisme ? | Recettes MDT | Somme des recettes mensuelles | Mois national, 2016-2023 |
| La recette progresse-t-elle ? | Variation annuelle | (Recettes annee / recettes annee precedente - 1) x 100 | Annee, comparaison a N-1, denominateur non nul |
| Quels marches arrivent ? | Arrivees | Somme des marches detailles, hors sous-totaux et % | Annee x marche, 2021-2023 |
| Quel est le poids d'un marche ? | Part de marche | Arrivees du marche / total national de la meme annee x 100 | Annee x marche |
| Quelle frequentation hoteliere ? | Nuitees | Somme des details non-residents + segment residents disjoint | Annee x marche/groupe, 2021-2023 |
| Quelle offre ? | Lits et etablissements | Somme des details region x categorie | Instantane 2023 |
| Quelle occupation ? | Taux detaille ou taux national publie | Taux source. Aucun total des taux, aucune moyenne simple | 2023 x region x categorie ; taux national publie : 38,7 % |
| Ou sont les investissements ? | Investissements MDT | Somme des milliers TND / 1 000 | Gouvernorat, instantane 2023 |
| Quels sites sont frequentes ? | Visiteurs de sites/musees | Somme des observations renseignees | Annee x site, 2019-2023 |
| Quel contexte de change ? | EUR/TND et USD/TND | Taux moyen mensuel BCT. Moyenne des mois seulement si agrege | Mois x devise, 2016-2023 |
| Quelle recette indicative en EUR ? | Recettes MEUR estimees | Somme, mois par mois, de recettes MDT / EUR_TND | Mois puis somme, valeur derivee non officielle |

La cible de prevision proposee pour S5 est `Recettes_MDT`. Les 96 observations mensuelles sont
regulieres et permettent une separation chronologique apprentissage/test. Les taux BCT pourront
servir de variables explicatives, a condition de ne pas utiliser leur valeur future inconnue.
Il ne faut pas deduire une causalite du seul rapprochement recettes/change.

Les arrivees aux frontieres et les nuitées hotelieres n'ont pas la meme population. Leur rapport
ne remplace pas la duree de sejour hoteliere officielle.
