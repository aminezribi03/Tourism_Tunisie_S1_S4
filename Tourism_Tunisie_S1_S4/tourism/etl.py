"""Extract -> Transform -> Load. Relancable, tracable, sans serveur SQL.

L'ETL reconstruit une base temporaire, controle son contenu puis la remplace.
Si une transformation echoue, la base precedente reste disponible.
"""
import argparse
import csv
import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tourism import __version__
from tourism.cleaning import category, is_total, market, month_key, number, parse_bct, region, text
from tourism.config import (BCT_CHECK_FILE, BCT_RAW_FILE, BCT_URL, ONTT_URL,
                            OUTPUT, RAW, SNAPSHOT_YEAR, TOURISM_FILE, MONTHS)

LOG = logging.getLogger(__name__)


def write_json(path, content):
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def write_csv(path, rows, columns=None):
    rows = list(rows)
    columns = columns or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _py(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


class Builder:
    def __init__(self, raw_dir, output_dir):
        self.raw = Path(raw_dir)
        self.output = Path(output_dir)
        self.tables = {}
        self.dimensions = {}
        self.issues = []
        self.controls = []
        self.inventory = []
        self.sheet_cache = {}
        self.started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def sheet(self, name):
        if name not in self.sheet_cache:
            df = pd.read_excel(self.raw / TOURISM_FILE, sheet_name=name, engine="openpyxl")
            df["SourceLigne"] = range(2, len(df) + 2)
            self.sheet_cache[name] = df
        return self.sheet_cache[name].copy()

    def issue(self, sheet, row, reason, value=None, level="INFO"):
        self.issues.append({"Feuille": sheet, "Ligne": int(row), "Niveau": level,
                            "Motif": reason, "Valeur_source": "" if value is None else str(value)})

    def control(self, name, actual, expected, tolerance=0.01, required=True):
        passed = actual is not None and abs(float(actual) - float(expected)) <= tolerance
        self.controls.append({"Controle": name, "Observe": actual, "Attendu": expected,
                              "Tolerance": tolerance, "Statut": "OK" if passed else "ECART",
                              "Bloquant": required})
        if required and not passed:
            raise ValueError(f"Controle echoue : {name}, observe={actual}, attendu={expected}")

    def dim(self, name, label, value, **attributes):
        members = self.dimensions.setdefault(name, {})
        if value not in members:
            members[value] = {name.removeprefix("dim_") + "Key": len(members) + 1,
                               label: value, **attributes}
        return next(iter(members[value].values()))

    def add(self, table, record, sheet, row, source=1):
        record = {k: _py(v) for k, v in record.items()}
        record.update(SourceKey=source, SourceFeuille=sheet, SourceLigne=int(row))
        self.tables.setdefault(table, []).append(record)

    def ref(self, sheet, row, label, value, unit, year=SNAPSHOT_YEAR):
        if value is not None:
            self.add("ref_controles_source", {"AnneeKey": int(year), "Libelle": label,
                     "Valeur": float(value), "Unite": unit}, sheet, row)

    def inventory_inputs(self):
        for path in sorted(self.raw.iterdir()):
            if path.is_file():
                info = {"Fichier": path.name, "Taille_octets": path.stat().st_size,
                        "SHA256": sha256(path)}
                if path.suffix == ".xlsx":
                    excel = pd.ExcelFile(path, engine="openpyxl")
                    info["Feuilles"] = []
                    for sheet in excel.sheet_names:
                        df = pd.read_excel(excel, sheet_name=sheet)
                        info["Feuilles"].append({"Nom": sheet, "Lignes": len(df),
                                                 "Colonnes": list(df.columns),
                                                 "Cellules_vides": int(df.isna().sum().sum()),
                                                 "Doublons_exacts": int(df.duplicated().sum())})
                self.inventory.append(info)

    def monthly(self):
        sheet = "Recettes_Mensuelles"
        df = self.sheet(sheet)
        for r in df.to_dict("records"):
            value = number(r["Recettes_touristiques_MDT"])
            if value is None or value < 0:
                raise ValueError("Recettes : valeur absente ou negative")
            self.add("fact_recettes", {"MoisKey": month_key(r["Annee"], r["Mois"]),
                     "Recettes_MDT": value}, sheet, r["SourceLigne"])
        keys = [r["MoisKey"] for r in self.tables["fact_recettes"]]
        self.control("Recettes : 96 mois", len(keys), 96, 0)
        self.control("Recettes : mois uniques", len(set(keys)), len(keys), 0)

        bct = parse_bct(self.raw / BCT_RAW_FILE)
        prepared = pd.read_excel(self.raw / BCT_CHECK_FILE, sheet_name="Source2_BCT_Change")
        prepared["MoisKey"] = prepared.Annee.astype(int) * 100 + prepared.Mois.astype(int)
        if prepared.MoisKey.duplicated().any():
            raise ValueError("Le fichier BCT de controle contient des dates dupliquees")
        joined = bct.merge(prepared, on="MoisKey", validate="one_to_one", how="outer", indicator=True)
        self.control("BCT HTML vs Excel : mois communs", int(joined._merge.eq("both").sum()), 96, 0)
        for currency in ["EUR", "USD"]:
            difference = (joined[f"{currency}_TND"] - joined[f"{currency}_TND_moyen"]).abs().max()
            self.control(f"BCT HTML vs Excel : ecart maximal {currency}", float(difference), 0, 0.00001)
        for i, r in bct.iterrows():
            for currency in ["EUR", "USD"]:
                self.add("fact_change", {"MoisKey": int(r.MoisKey), "DeviseKey": self.dim(
                    "dim_Devise", "Devise", currency), "Taux_TND": float(r[f"{currency}_TND"])},
                    "BCT_HTML", int(i) + 2, source=2)
        self.control("Recettes/BCT : memes mois", len(set(keys) & set(bct.MoisKey)), 96, 0)
        # L'echantillon est un controle supplementaire, jamais une deuxieme source ajoutee.
        sample_path = self.raw / "Echantillon_donnees_Tourisme_Tunisie.xlsx"
        if sample_path.exists():
            sample = pd.read_excel(sample_path, sheet_name="Echantillon_Recettes")
            sample["MoisKey"] = sample.Annee * 100 + sample.Mois_num
            merged = pd.DataFrame(self.tables["fact_recettes"]).merge(sample, on="MoisKey", validate="one_to_one")
            self.control("Echantillon recettes : mois compares", len(merged), 96, 0)
            self.control("Echantillon recettes : ecart maximal", float((merged.Recettes_MDT - merged.Recettes_touristiques_MDT).abs().max()), 0)

    def nationalities(self):
        specs = [("Arrivees_Nationalite", "Nombre_arrivees", "fact_arrivees", "Arrivees"),
                 ("Nuitees_Nationalite", "Nombre_nuitees", "fact_nuitees", "Nuitees"),
                 ("Arrivees_Saison", "Arrivees", "fact_arrivees_saison", "Arrivees")]
        for sheet, column, table, measure in specs:
            for r in self.sheet(sheet).to_dict("records"):
                key = text(r["Nationalite"])
                value = number(r[column])
                # Moyen-Orient : sous-total dans les arrivees annuelles, seul groupe disponible dans les autres tables.
                aggregate = is_total(key) or key == "AFR,JAP,AUST,CHIN,BR,DIV"
                aggregate |= sheet == "Arrivees_Nationalite" and key == "MOYENS ORIENTAUX"
                # Les residents forment un segment distinct et disjoint des non-residents.
                resident = table == "fact_nuitees" and key == "TOTAL RESIDENTS"
                if aggregate and not resident:
                    self.issue(sheet, r["SourceLigne"], "Total, sous-total ou pourcentage : exclu du detail", value)
                    label = r["Nationalite"]
                    if table == "fact_arrivees_saison":
                        label += " / " + r["Saison"]
                    self.ref(sheet, r["SourceLigne"], label, value, "Pourcentage" if key == "%" else measure, int(r["Annee"]))
                    continue
                if value is None:
                    self.issue(sheet, r["SourceLigne"], "Valeur manquante : conservee NULL", level="ATTENTION")
                if value is not None and (value < 0 or value != int(value)):
                    raise ValueError(f"{sheet} : compte invalide ligne {r['SourceLigne']}")
                label = market(r["Nationalite"])
                kind = "Residents" if resident else ("Groupe" if label in {"MOYENS ORIENTAUX", "DIVERS EUROPEENS", "AFRICAINS", "DIVERS", "SCANDINAVES"} else "Marche")
                record = {"AnneeKey": int(r["Annee"]), "MarcheKey": self.dim("dim_Marche", "Marche", label, Type=kind),
                          measure: int(value) if value is not None else None}
                if table == "fact_arrivees_saison":
                    record["SaisonKey"] = self.dim("dim_Saison", "Saison", text(r["Saison"]))
                self.add(table, record, sheet, r["SourceLigne"])

    def supply(self):
        sheet = "Capacite_Hoteliere"
        for r in self.sheet(sheet).to_dict("records"):
            if is_total(r["Region"]):
                self.ref(sheet, r["SourceLigne"], "Lits / " + str(r["Categorie_hebergement"]), number(r["Nombre_lits"]), "Lits")
                self.issue(sheet, r["SourceLigne"], "Total national : utilise seulement pour reconciliation")
                continue
            self.add("fact_capacite", {"AnneeKey": SNAPSHOT_YEAR,
                     "RegionKey": self.dim("dim_Region", "Region", region(r["Region"])),
                     "CategorieKey": self.dim("dim_Categorie", "Categorie", category(r["Categorie_hebergement"])),
                     "Lits": number(r["Nombre_lits"]), "Etablissements": number(r["Nombre_etablissements"])}, sheet, r["SourceLigne"])

        sheet = "Taux_Occupation"
        for r in self.sheet(sheet).to_dict("records"):
            value = number(r["Taux_occupation_pct"])
            if is_total(r["Categorie_hebergement"]) or text(r["Region"]) == "MOYENNE":
                self.ref(sheet, r["SourceLigne"], str(r["Region"]) + " / " + str(r["Categorie_hebergement"]), value, "%")
                self.issue(sheet, r["SourceLigne"], "Moyenne source : separee des taux detailles", value)
                continue
            if value is not None and not 0 <= value <= 100:
                self.issue(sheet, r["SourceLigne"], "Taux hors de 0 a 100 : valeur en quarantaine, taux charge NULL", value, level="ATTENTION")
                value = None
            if value is None:
                self.issue(sheet, r["SourceLigne"], "Taux absent : conserve NULL, pas zero", level="ATTENTION")
            self.add("fact_occupation", {"AnneeKey": SNAPSHOT_YEAR,
                     "RegionKey": self.dim("dim_Region", "Region", region(r["Region"])),
                     "CategorieKey": self.dim("dim_Categorie", "Categorie", category(r["Categorie_hebergement"])),
                     "Taux_pct": value}, sheet, r["SourceLigne"])

        sheet = "Investissements"
        for r in self.sheet(sheet).to_dict("records"):
            if is_total(r["Gouvernorat"]):
                self.ref(sheet, r["SourceLigne"], "Investissement total", number(r["Invest_total_milliers_DT"]), "Milliers TND")
                self.issue(sheet, r["SourceLigne"], "Total national : non charge dans le detail")
                continue
            self.add("fact_investissements", {"AnneeKey": SNAPSHOT_YEAR,
                     "GouvernoratKey": self.dim("dim_Gouvernorat", "Gouvernorat", region(r["Gouvernorat"])),
                     "Capacite_lits": number(r["Capacite_hoteliere_lits"]),
                     "Hebergement_kTND": number(r["Invest_hebergement_milliers_DT"]),
                     "Animation_kTND": number(r["Invest_animation_milliers_DT"]),
                     "Total_kTND": number(r["Invest_total_milliers_DT"])}, sheet, r["SourceLigne"])

    def other(self):
        sheet = "Visiteurs_Sites"
        for r in self.sheet(sheet).to_dict("records"):
            value = number(r["Nombre_visiteurs"])
            if is_total(r["Site_musee"]):
                self.ref(sheet, r["SourceLigne"], "Visiteurs sites total", value, "Visiteurs", int(r["Annee"]))
                self.issue(sheet, r["SourceLigne"], "Total separe du detail")
                continue
            if value is None:
                self.issue(sheet, r["SourceLigne"], "Visiteurs absents : conserve NULL", level="ATTENTION")
            self.add("fact_sites", {"AnneeKey": int(r["Annee"]),
                     "SiteKey": self.dim("dim_Site", "Site", str(r["Site_musee"]).strip()),
                     "Visiteurs": value}, sheet, r["SourceLigne"])

        sheet = "Agences_Voyages"
        for r in self.sheet(sheet).to_dict("records"):
            value = number(r["Nombre_agences"])
            if is_total(r["Region"]) or is_total(r["Licence"]):
                if is_total(r["Region"]) and is_total(r["Licence"]):
                    self.ref(sheet, r["SourceLigne"], "Agences total", value, "Agences", int(r["Annee"]))
                self.issue(sheet, r["SourceLigne"], "Total exclu du detail")
                continue
            if value is None:
                self.issue(sheet, r["SourceLigne"], "Nombre agences absent : conserve NULL", level="ATTENTION")
            self.add("fact_agences", {"AnneeKey": int(r["Annee"]),
                     "RegionKey": self.dim("dim_Region", "Region", region(r["Region"])),
                     "LicenceKey": self.dim("dim_Licence", "Licence", text(r["Licence"])),
                     "Agences": value}, sheet, r["SourceLigne"])

        sheet = "Restaurants"
        categories = ["3_fourchettes_luxe", "3_fourchettes", "2_fourchettes", "1_fourchette"]
        for r in self.sheet(sheet).to_dict("records"):
            if is_total(r["Region"]):
                self.ref(sheet, r["SourceLigne"], "Restaurants total", number(r["Total"]), "Restaurants")
                self.issue(sheet, r["SourceLigne"], "Total national exclu du detail")
                continue
            for cat in categories:
                value = number(r[cat])
                if value is None:
                    self.issue(sheet, r["SourceLigne"], f"{cat} absent : conserve NULL", level="ATTENTION")
                self.add("fact_restaurants", {"AnneeKey": SNAPSHOT_YEAR,
                         "RegionKey": self.dim("dim_Region", "Region", region(r["Region"])),
                         "ClasseRestaurantKey": self.dim("dim_ClasseRestaurant", "ClasseRestaurant", text(cat)),
                         "Restaurants": value}, sheet, r["SourceLigne"])

        sheet = "Duree_Nationalite"
        for r in self.sheet(sheet).to_dict("records"):
            value = number(r["Valeur"])
            if is_total(r["Nationalite"]):
                self.ref(sheet, r["SourceLigne"], str(r["Indicateur"]), value,
                         "Ratio" if r["Indicateur"] == "Coefficient_mobilite" else "Jours", int(r["Annee"]))
                self.issue(sheet, r["SourceLigne"], "Moyenne annuelle separee")
                continue
            self.add("fact_duree_marche", {"AnneeKey": int(r["Annee"]),
                     "MarcheKey": self.dim("dim_Marche", "Marche", market(r["Nationalite"]), Type="Marche"),
                     "IndicateurKey": self.dim("dim_Indicateur", "Indicateur", str(r["Indicateur"]),
                     Unite="Ratio" if r["Indicateur"] == "Coefficient_mobilite" else "Jours"),
                     "Valeur": value}, sheet, r["SourceLigne"])

        # Deux blocs par region ont perdu leur libelle dans le fichier fourni.
        # Les charger sous une meme cle ferait croire a un doublon ou melangerait les populations.
        for r in self.sheet("Duree_Region").to_dict("records"):
            self.issue("Duree_Region", r["SourceLigne"],
                       "Bloc sans libelle de population : en quarantaine, aucune moyenne calculee", level="ATTENTION")

        for r in self.sheet("KPI_2023").to_dict("records"):
            self.ref("KPI_2023", r["SourceLigne"], r["Indicateur"], number(r["Valeur"]), str(r["Unite"]), int(r["Annee"]))
        for r in self.sheet("Recettes_Trimestrielles").to_dict("records"):
            self.ref("Recettes_Trimestrielles", r["SourceLigne"], str(r["Trimestre"]),
                     number(r["Recettes_MDT"]), "MDT", int(r["Annee"]))
            self.issue("Recettes_Trimestrielles", r["SourceLigne"], "Reference trimestrielle : non additionnee aux mois")

    def validate_records(self):
        # Grain explicite : les lignes sources ne font jamais partie de la cle metier.
        grains = {
            "fact_recettes": ["MoisKey"], "fact_change": ["MoisKey", "DeviseKey"],
            "fact_arrivees": ["AnneeKey", "MarcheKey"], "fact_nuitees": ["AnneeKey", "MarcheKey"],
            "fact_arrivees_saison": ["AnneeKey", "MarcheKey", "SaisonKey"],
            "fact_capacite": ["AnneeKey", "RegionKey", "CategorieKey"],
            "fact_occupation": ["AnneeKey", "RegionKey", "CategorieKey"],
            "fact_investissements": ["AnneeKey", "GouvernoratKey"],
            "fact_sites": ["AnneeKey", "SiteKey"],
            "fact_agences": ["AnneeKey", "RegionKey", "LicenceKey"],
            "fact_restaurants": ["AnneeKey", "RegionKey", "ClasseRestaurantKey"],
            "fact_duree_marche": ["AnneeKey", "MarcheKey", "IndicateurKey"],
        }
        self.grains = grains
        for table, grain in grains.items():
            frame = pd.DataFrame(self.tables[table])
            if frame.duplicated(grain).any():
                raise ValueError(f"{table} : cle metier dupliquee {grain}")
        # Valeurs nationales lues de la source, pas somme detail + totaux.
        for sheet, table, measure in [("Arrivees_Nationalite", "fact_arrivees", "Arrivees"),
                                       ("Nuitees_Nationalite", "fact_nuitees", "Nuitees")]:
            raw = self.sheet(sheet)
            for year in [2021, 2022, 2023]:
                expected = raw.loc[raw.Annee.eq(year) & raw.Nationalite.map(text).eq("TOTAL GENERAL")].iloc[0]
                column = "Nombre_arrivees" if measure == "Arrivees" else "Nombre_nuitees"
                actual = sum(r[measure] for r in self.tables[table] if r["AnneeKey"] == year and r[measure] is not None)
                self.control(f"{measure} {year} : detail vs total publie", actual, float(expected[column]), 0, required=False)
        totals = self.sheet("Capacite_Hoteliere")
        national = totals[totals.Region.map(is_total)]
        self.control("Lits 2023 : detail vs total", sum(r["Lits"] for r in self.tables["fact_capacite"]), float(national.Nombre_lits.sum()), 0)
        self.control("Etablissements 2023 : detail vs total", sum(r["Etablissements"] for r in self.tables["fact_capacite"]), float(national.Nombre_etablissements.sum()), 0)
        inv = self.sheet("Investissements")
        expected = inv.loc[inv.Gouvernorat.map(is_total), "Invest_total_milliers_DT"].iloc[0]
        self.control("Investissements : detail vs total", sum(r["Total_kTND"] for r in self.tables["fact_investissements"]), float(expected), 0)
        kpis = self.sheet("KPI_2023")
        revenue_ref = kpis.loc[kpis.Indicateur.eq("Recettes touristiques"), "Valeur"].iloc[0]
        revenue = sum(r["Recettes_MDT"] for r in self.tables["fact_recettes"] if r["MoisKey"] // 100 == 2023)
        self.control("Recettes 2023 : somme mois vs synthese", revenue, float(revenue_ref))
        # Presence de chaque mois, sans interpolation ni repetitions annuelles.
        observed = sorted(r["MoisKey"] for r in self.tables["fact_recettes"])
        expected = [y * 100 + m for y in range(2016, 2024) for m in range(1, 13)]
        self.control("Calendrier mensuel : mois absents", len(set(expected) - set(observed)), 0, 0)

    def load(self, temp):
        con = sqlite3.connect(temp)
        con.execute("PRAGMA foreign_keys = ON")
        years = list(range(2016, 2024))
        con.execute("CREATE TABLE dim_Annee (AnneeKey INTEGER PRIMARY KEY, Annee INTEGER NOT NULL UNIQUE)")
        con.executemany("INSERT INTO dim_Annee VALUES (?,?)", [(y, y) for y in years])
        con.execute("CREATE TABLE dim_Mois (MoisKey INTEGER PRIMARY KEY, Date TEXT NOT NULL UNIQUE, AnneeKey INTEGER NOT NULL REFERENCES dim_Annee(AnneeKey), Mois INTEGER NOT NULL CHECK(Mois BETWEEN 1 AND 12), MoisNom TEXT NOT NULL, Trimestre INTEGER NOT NULL)")
        names = {v: k.capitalize() for k, v in MONTHS.items()}
        con.executemany("INSERT INTO dim_Mois VALUES (?,?,?,?,?,?)", [
            (y * 100 + m, f"{y}-{m:02d}-01", y, m, names[m], (m - 1) // 3 + 1)
            for y in years for m in range(1, 13)])
        con.execute("CREATE TABLE dim_Source (SourceKey INTEGER PRIMARY KEY, Organisme TEXT NOT NULL, Fichier TEXT NOT NULL, URL TEXT NOT NULL, Extraction_originale TEXT, Licence TEXT, Note TEXT NOT NULL)")
        con.executemany("INSERT INTO dim_Source VALUES (?,?,?,?,?,?,?)", [
            (1, "ONTT (transcription fournie)", TOURISM_FILE, ONTT_URL, None, None,
             "Rapport Tourisme tunisien en chiffres, Extrait 2023. Date originale et licence non fournies. Les tables sans annee sont des instantanes 2023. PDF original non fourni ; transcription a confirmer avec le rapport officiel."),
            (2, "Banque Centrale de Tunisie", BCT_RAW_FILE, BCT_URL, None, None,
             "Export HTML brut fourni. Unite : TND pour 1 EUR ou 1 USD. Serie janvier 2016-decembre 2023.")])
        for table, members in self.dimensions.items():
            records = list(members.values())
            columns = list(records[0])
            ddl = [f'"{columns[0]}" INTEGER PRIMARY KEY'] + [f'"{c}" TEXT NOT NULL' for c in columns[1:]]
            con.execute(f'CREATE TABLE "{table}" ({", ".join(ddl)})')
            marks = ",".join("?" for _ in columns)
            con.executemany(f'INSERT INTO "{table}" VALUES ({marks})', [[r[c] for c in columns] for r in records])
        key_tables = {table.removeprefix("dim_") + "Key": table for table in self.dimensions}
        key_tables.update(AnneeKey="dim_Annee", MoisKey="dim_Mois", SourceKey="dim_Source")
        for table, records in self.tables.items():
            columns = list(records[0])
            ddl = ["ObservationKey INTEGER PRIMARY KEY"]
            for c in columns:
                if c in key_tables:
                    ddl.append(f'"{c}" INTEGER NOT NULL REFERENCES "{key_tables[c]}"("{c}")')
                elif c == "SourceLigne":
                    ddl.append(f'"{c}" INTEGER NOT NULL')
                elif c in {"SourceFeuille", "Libelle", "Unite"}:
                    ddl.append(f'"{c}" TEXT NOT NULL')
                else:
                    ddl.append(f'"{c}" REAL CHECK("{c}" >= 0)')
            if table in self.grains:
                ddl.append("UNIQUE (" + ",".join(self.grains[table]) + ")")
            con.execute(f'CREATE TABLE "{table}" ({", ".join(ddl)})')
            marks = ",".join("?" for _ in columns)
            column_sql = ",".join(f'"{c}"' for c in columns)
            con.executemany(f'INSERT INTO "{table}" ({column_sql}) VALUES ({marks})', [[r[c] for c in columns] for r in records])
        con.execute("CREATE TABLE fact_previsions (MoisKey INTEGER NOT NULL REFERENCES dim_Mois(MoisKey), Modele TEXT NOT NULL, Cible TEXT NOT NULL, Valeur_MDT REAL NOT NULL, Borne_basse REAL, Borne_haute REAL, Date_entrainement TEXT NOT NULL, PRIMARY KEY(MoisKey,Modele,Cible))")
        # Pas de fausses previsions en semaine 4. En S5, etendre d'abord dim_Annee et dim_Mois.
        con.execute("CREATE TABLE etl_execution (ExecutionKey INTEGER PRIMARY KEY, Debut_UTC TEXT NOT NULL, Version TEXT NOT NULL, Statut TEXT NOT NULL)")
        con.execute("INSERT INTO etl_execution VALUES (1,?,?,?)", (self.started, __version__, "OK"))
        con.execute("""CREATE VIEW vw_recettes_change AS
            SELECT m.MoisKey, m.Date, m.AnneeKey AS Annee, m.Mois, m.MoisNom, m.Trimestre,
                   r.Recettes_MDT,
                   MAX(CASE WHEN d.Devise='EUR' THEN c.Taux_TND END) AS EUR_TND,
                   MAX(CASE WHEN d.Devise='USD' THEN c.Taux_TND END) AS USD_TND,
                   r.Recettes_MDT/MAX(CASE WHEN d.Devise='EUR' THEN c.Taux_TND END) AS Recettes_MEUR_estimees,
                   r.Recettes_MDT/MAX(CASE WHEN d.Devise='USD' THEN c.Taux_TND END) AS Recettes_MUSD_estimees
            FROM fact_recettes r JOIN dim_Mois m USING(MoisKey)
            JOIN fact_change c USING(MoisKey) JOIN dim_Devise d USING(DeviseKey)
            GROUP BY m.MoisKey, r.Recettes_MDT""")
        for fact, view, dimension, key, label in [
            ("fact_arrivees", "vw_arrivees", "dim_Marche", "MarcheKey", "Marche"),
            ("fact_nuitees", "vw_nuitees", "dim_Marche", "MarcheKey", "Marche"),
            ("fact_sites", "vw_sites", "dim_Site", "SiteKey", "Site"),
            ("fact_investissements", "vw_investissements", "dim_Gouvernorat", "GouvernoratKey", "Gouvernorat")]:
            con.execute(f'CREATE VIEW {view} AS SELECT f.*, d."{label}" FROM {fact} f JOIN {dimension} d USING({key})')
        for fact, view in [("fact_capacite", "vw_capacite"), ("fact_occupation", "vw_occupation")]:
            con.execute(f'CREATE VIEW {view} AS SELECT f.*, r.Region, c.Categorie FROM {fact} f JOIN dim_Region r USING(RegionKey) JOIN dim_Categorie c USING(CategorieKey)')
        violations = con.execute("PRAGMA foreign_key_check").fetchall()
        self.control("DWH : cles etrangeres invalides", len(violations), 0, 0)
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError("Integrite SQLite : " + integrity)
        con.commit()
        schema = "\n\n".join(row[0] + ";" for row in con.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"))
        (self.output / "schema.sql").write_text("PRAGMA foreign_keys=ON;\n\n" + schema, encoding="utf-8")
        return con

    def run(self):
        start = time.perf_counter()
        self.output.mkdir(parents=True, exist_ok=True)
        export = self.output / "powerbi_csv"
        export.mkdir(exist_ok=True)
        for filename in [TOURISM_FILE, BCT_RAW_FILE, BCT_CHECK_FILE]:
            if not (self.raw / filename).is_file():
                raise FileNotFoundError(f"Fichier requis absent : {self.raw / filename}")
        self.inventory_inputs()
        self.monthly()
        self.nationalities()
        self.supply()
        self.other()
        self.validate_records()
        temp = self.output / f".tourisme_{os.getpid()}.tmp.sqlite"
        con = None
        try:
            con = self.load(temp)
            names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")]
            counts = {}
            for table in names:
                frame = pd.read_sql_query(f'SELECT * FROM "{table}"', con)
                frame.to_csv(export / f"{table}.csv", index=False, encoding="utf-8-sig", float_format="%.10g")
                counts[table] = len(frame)
            con.close()
            con = None
            temp.replace(self.output / "tourisme.sqlite")
        finally:
            if con is not None:
                con.close()
            if temp.exists():
                temp.unlink()
        report = {"version": __version__, "execution_utc": self.started,
                  "duree_secondes": round(time.perf_counter() - start, 3), "statut": "OK",
                  "observations": counts, "controles": self.controls,
                  "ecarts_non_bloquants": sum(c["Statut"] != "OK" for c in self.controls),
                  "lignes_audit": len(self.issues),
                  "limites": ["Date d'extraction originale et licence non fournies : a confirmer.",
                              "Source ONTT : transcription Excel fournie, PDF original non fourni.",
                              "Duree_Region : deux blocs sans libelle, exclus du DWH.",
                              "Instantanes capacite/occupation/investissements/restaurants : 2023.",
                              "Aucune prevision creee : reserve a la semaine 5."]}
        write_json(self.output / "rapport_qualite.json", report)
        write_json(self.output / "inventaire_sources.json", self.inventory)
        write_json(self.output / "grains.json", self.grains)
        write_csv(self.output / "audit_lignes.csv", self.issues)
        write_csv(self.output / "controles.csv", self.controls)
        write_csv(self.output / "fichiers_sha256.csv", [{k: r[k] for k in ["Fichier", "Taille_octets", "SHA256"]} for r in self.inventory])
        LOG.info("ETL termine : %s, %s tables/vues", self.output / "tourisme.sqlite", len(counts))
        return report


def run_pipeline(raw_dir=RAW, output_dir=OUTPUT):
    return Builder(raw_dir, output_dir).run()


def main():
    parser = argparse.ArgumentParser(description="Construire le DWH tourisme")
    parser.add_argument("--raw-dir", type=Path, default=RAW)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    try:
        report = run_pipeline(args.raw_dir, args.output_dir)
    except Exception:
        LOG.exception("ETL echoue. La base precedente est conservee.")
        raise SystemExit(1)
    print(json.dumps({"statut": report["statut"], "secondes": report["duree_secondes"],
                      "ecarts_a_examiner": report["ecarts_non_bloquants"]}, indent=2))


if __name__ == "__main__":
    main()
