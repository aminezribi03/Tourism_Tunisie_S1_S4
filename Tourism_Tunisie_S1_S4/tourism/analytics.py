"""Lecture seule du DWH et calculs partages par l'interface et les tests."""
import json
import sqlite3
from contextlib import closing

import pandas as pd

from tourism.config import DB, OUTPUT

ALLOWED = {
    "vw_recettes_change", "vw_arrivees", "vw_nuitees", "vw_sites", "vw_investissements",
    "vw_capacite", "vw_occupation", "fact_arrivees_saison", "fact_agences",
    "fact_restaurants", "fact_duree_marche", "dim_Marche", "dim_Saison", "dim_Region",
    "dim_Licence", "dim_ClasseRestaurant", "dim_Indicateur", "dim_Source",
    "ref_controles_source", "fact_previsions", "dim_Mois", "dim_Annee",
}


def connect(db=DB):
    # mode=ro interdit de creer une base vide si le chemin est incorrect.
    return sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)


def read_table(name, db=DB):
    if name not in ALLOWED:
        raise ValueError("Table non autorisee")
    with closing(connect(db)) as con:
        return pd.read_sql_query(f'SELECT * FROM "{name}"', con)


def monthly(db=DB):
    frame = read_table("vw_recettes_change", db)
    frame["Date"] = pd.to_datetime(frame.Date)
    return frame.sort_values("Date").reset_index(drop=True)


def safe_sum(values):
    """Une selection sans observation reste indisponible, pas 0."""
    if len(values) == 0 or values.notna().sum() == 0:
        return None
    return float(values.sum(min_count=1))


def yoy(current, previous):
    if current is None or previous is None or previous == 0:
        return None
    return (current / previous - 1) * 100


def money(value, decimals=1):
    if value is None or pd.isna(value):
        return "n.d."
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def summary(year, db=DB):
    revenue = monthly(db)
    arrivals = read_table("vw_arrivees", db)
    nights = read_table("vw_nuitees", db)
    selected = revenue[revenue.Annee.eq(year)]
    return {
        "recettes": safe_sum(selected.Recettes_MDT),
        "recettes_yoy": yoy(safe_sum(selected.Recettes_MDT), safe_sum(revenue.loc[revenue.Annee.eq(year-1), "Recettes_MDT"])),
        "arrivees": safe_sum(arrivals.loc[arrivals.AnneeKey.eq(year), "Arrivees"]),
        "nuitees": safe_sum(nights.loc[nights.AnneeKey.eq(year), "Nuitees"]),
    }


def quality(output=OUTPUT):
    return json.loads((output / "rapport_qualite.json").read_text(encoding="utf-8"))
