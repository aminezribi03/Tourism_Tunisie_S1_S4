"""Genere un vrai projet PBIP/PBIR a partir du DWH, avec import CSV et DAX.

A lancer apres extraction sur un nouveau PC, ou apres reconstruction de l'ETL.
Fermer Power BI avant de regenerer ces fichiers. Aucune publication automatique.
"""
import argparse
import json
import sqlite3
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tourism.config import OUTPUT  # noqa: E402

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


MEASURES = {
    "Recettes MDT": ("SUM(fact_recettes[Recettes_MDT])", "#,0.0"),
    "Recettes annee precedente": ("VAR An = SELECTEDVALUE(dim_Annee[AnneeKey])\nRETURN IF(NOT ISBLANK(An), CALCULATE([Recettes MDT], REMOVEFILTERS(dim_Annee), dim_Annee[AnneeKey] = An - 1))", "#,0.0"),
    "Variation recettes %": ("DIVIDE([Recettes MDT] - [Recettes annee precedente], [Recettes annee precedente])", "0.0%"),
    "Arrivees": ("SUM(fact_arrivees[Arrivees])", "#,0"),
    "Part du marche %": ("DIVIDE([Arrivees], CALCULATE([Arrivees], REMOVEFILTERS(dim_Marche)))", "0.0%"),
    "Nuitees": ("SUM(fact_nuitees[Nuitees])", "#,0"),
    "Arrivees par saison": ("SUM(fact_arrivees_saison[Arrivees])", "#,0"),
    "Lits": ("SUM(fact_capacite[Lits])", "#,0"),
    "Etablissements": ("SUM(fact_capacite[Etablissements])", "#,0"),
    "Investissements MDT": ("DIVIDE(SUM(fact_investissements[Total_kTND]), 1000)", "#,0.000"),
    "Visiteurs sites": ("SUM(fact_sites[Visiteurs])", "#,0"),
    "Taux occupation detail %": ("IF(HASONEVALUE(fact_occupation[ObservationKey]), DIVIDE(MAX(fact_occupation[Taux_pct]), 100))", "0.0%"),
    "Occupation nationale publiee %": ("IF(ISFILTERED(dim_Region) || ISFILTERED(dim_Categorie), BLANK(), DIVIDE(CALCULATE(MAX(ref_controles_source[Valeur]), ref_controles_source[SourceFeuille] = \"KPI_2023\", ref_controles_source[Libelle] = \"Taux occupation moyen\"), 100))", "0.0%"),
    "EUR TND moyen": ("CALCULATE(AVERAGE(fact_change[Taux_TND]), dim_Devise[Devise] = \"EUR\")", "0.0000"),
    "USD TND moyen": ("CALCULATE(AVERAGE(fact_change[Taux_TND]), dim_Devise[Devise] = \"USD\")", "0.0000"),
    "Recettes MEUR estimees": ("SUMX(fact_recettes, VAR MoisCourant = fact_recettes[MoisKey] VAR Taux = CALCULATE(MAX(fact_change[Taux_TND]), dim_Devise[Devise] = \"EUR\", fact_change[MoisKey] = MoisCourant) RETURN DIVIDE(fact_recettes[Recettes_MDT], Taux))", "#,0.0"),
    "Previsions MDT": ("SUM(fact_previsions[Valeur_MDT])", "#,0.0"),
}


def field(table, column, measure=False, active=None):
    expr = {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}
    result = {"field": {"Measure" if measure else "Column": expr},
              "queryRef": f"{table}.{column}", "nativeQueryRef": column}
    if active is not None:
        result["active"] = active
    return result


def mfield(name):
    return field("fact_recettes", name, True)


def literal(value):
    if isinstance(value, bool):
        return {"expr": {"Literal": {"Value": str(value).lower()}}}
    return {"expr": {"Literal": {"Value": "'" + str(value).replace("'", "''") + "'"}}}


def visual(root, page, name, visual_type, roles, title, x, y, width, height, sort=None):
    query = {"queryState": {role: {"projections": fields} for role, fields in roles.items()}}
    if sort:
        query["sortDefinition"] = {"sort": [{"field": sort[0]["field"], "direction": sort[1]}], "isDefaultSort": True}
    data = {"$schema": SCHEMA + "visualContainer/2.4.0/schema.json", "name": name,
            "position": {"x": x, "y": y, "z": 0, "height": height, "width": width, "tabOrder": y + x},
            "visual": {"visualType": visual_type, "query": query,
                       "drillFilterOtherVisuals": True,
                       "visualContainerObjects": {
                           "title": [{"properties": {"show": literal(True), "text": literal(title)}}],
                           "background": [{"properties": {"show": literal(True), "color": {"solid": {"color": literal("#FFFFFF")}}, "transparency": {"expr": {"Literal": {"Value": "0D"}}}}}]
                       }}}
    save(root / "Tourisme.Report" / "definition" / "pages" / page / "visuals" / name / "visual.json", data)


def build(destination=None, output=OUTPUT, portable_example=False):
    destination = Path(destination or ROOT / "powerbi")
    model_path = destination / "Tourisme.SemanticModel"
    report_path = destination / "Tourisme.Report"
    csv_path = "C:/Tourism_Tunisie_S1_S4/outputs/powerbi_csv/" if portable_example else (Path(output) / "powerbi_csv").resolve().as_posix() + "/"
    db_path = Path(output) / "tourisme.sqlite"
    con = sqlite3.connect(db_path)
    tables = []
    relationships = []
    # Les vues sont reservees aux exports plats. Le modele Power BI emploie les vraies tables dimensionnelles.
    names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'etl_execution' ORDER BY name")]
    for table in names:
        info = con.execute(f'PRAGMA table_info("{table}")').fetchall()
        columns, transforms = [], []
        for _, name, sql_type, _, _, pk in info:
            is_date = table == "dim_Mois" and name == "Date"
            kind = "dateTime" if is_date else ("int64" if sql_type == "INTEGER" else "double" if sql_type == "REAL" else "string")
            c = {"name": name, "dataType": kind, "sourceColumn": name, "summarizeBy": "none"}
            if name.endswith("Key") or name.startswith("Source"):
                c["isHidden"] = True
            if pk and table.startswith("dim_"):
                c["isKey"] = True
            if is_date:
                c["formatString"] = "mmm yyyy"
            if table == "dim_Mois" and name == "MoisNom":
                c["sortByColumn"] = "Mois"
            columns.append(c)
            mtype = "type datetime" if is_date else "Int64.Type" if kind == "int64" else "type number" if kind == "double" else "type text"
            transforms.append('{"' + name + '", ' + mtype + '}')
        partition = ["let", f'    Source = Csv.Document(File.Contents(RootPath & "{table}.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
                     '    Entetes = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),',
                     '    Types = Table.TransformColumnTypes(Entetes, {' + ", ".join(transforms) + '}, "en-US")', "in", "    Types"]
        t = {"name": table, "columns": columns,
             "partitions": [{"name": table, "mode": "import", "source": {"type": "m", "expression": partition}}]}
        if table in {"ref_controles_source", "dim_Source"}:
            t["isHidden"] = True
        if table == "fact_recettes":
            t["measures"] = [{"name": name, "expression": expression.splitlines(), "formatString": fmt,
                               "displayFolder": "KPI"} for name, (expression, fmt) in MEASURES.items()]
        if table == "dim_Mois":
            t["hierarchies"] = [{"name": "Calendrier", "levels": [
                {"name": "Annee", "ordinal": 0, "column": "AnneeKey"},
                {"name": "Trimestre", "ordinal": 1, "column": "Trimestre"},
                {"name": "Mois", "ordinal": 2, "column": "MoisNom"}]}]
        tables.append(t)
        for fk in con.execute(f'PRAGMA foreign_key_list("{table}")').fetchall():
            _, _, target, source_column, target_column, *_ = fk
            relationships.append({"name": str(uuid.uuid5(uuid.NAMESPACE_URL, f"tourisme/{table}/{source_column}/{target}")),
                                  "fromTable": table, "fromColumn": source_column,
                                  "toTable": target, "toColumn": target_column,
                                  "crossFilteringBehavior": "oneDirection", "isActive": True})
    con.close()
    model = {"name": "Tourisme_Tunisie", "compatibilityLevel": 1600,
             "model": {"culture": "fr-FR", "sourceQueryCulture": "en-US", "defaultPowerBIDataSourceVersion": "powerBI_V3",
                       "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": False},
                       "expressions": [{"name": "RootPath", "kind": "m", "expression": json.dumps(csv_path) + ' meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'}],
                       "tables": tables, "relationships": relationships,
                       "annotations": [{"name": "PBI_ProTooling", "value": '["DevMode"]'}]}}
    save(model_path / "model.bim", model)
    platform_schema = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
    for folder, item_type in [(model_path, "SemanticModel"), (report_path, "Report")]:
        save(folder / ".platform", {"$schema": platform_schema,
             "metadata": {"type": item_type, "displayName": "Tourisme Tunisie"},
             "config": {"version": "2.0", "logicalId": str(uuid.uuid5(uuid.NAMESPACE_URL, "tourisme-tunisie-s1-s4/" + item_type))}})
    save(model_path / "definition.pbism", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json", "version": "1.0", "settings": {}})
    save(destination / "Tourisme_Tunisie.pbip", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0", "artifacts": [{"report": {"path": "Tourisme.Report"}}], "settings": {"enableAutoRecovery": True}})
    save(report_path / "definition.pbir", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json", "version": "4.0", "datasetReference": {"byPath": {"path": "../Tourisme.SemanticModel"}}})
    definition = report_path / "definition"
    save(definition / "version.json", {"$schema": SCHEMA + "versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    save(definition / "report.json", {"$schema": SCHEMA + "report/1.0.0/schema.json",
         "themeCollection": {"baseTheme": {"name": "CY24SU06", "reportVersionAtImport": "5.55", "type": "SharedResources"}},
         "layoutOptimization": "None"})
    pages = [("recettes", "Recettes et change"), ("marches", "Marches et saisons"),
             ("hebergement", "Hebergement 2023"), ("territoires", "Investissements et patrimoine"),
             ("previsions", "Previsions - semaine 5")]
    save(definition / "pages" / "pages.json", {"$schema": SCHEMA + "pagesMetadata/1.1.0/schema.json", "pageOrder": [p[0] for p in pages], "activePageName": "recettes"})
    for name, display in pages:
        save(definition / "pages" / name / "page.json", {"$schema": SCHEMA + "page/1.0.0/schema.json", "name": name, "displayName": display, "displayOption": "FitToPage", "width": 1280, "height": 800})
    def v(page, name, kind, roles, title, x, y, w, h, sort=None):
        visual(destination, page, name, kind, roles, title, x, y, w, h, sort)
    v("recettes", "annee_recettes", "slicer", {"Values": [field("dim_Annee", "Annee")]}, "Annee", 20, 15, 200, 100)
    for i, (name, label) in enumerate([("Recettes MDT", "Recettes (MDT)"), ("Variation recettes %", "Variation annuelle"), ("EUR TND moyen", "EUR/TND moyen")]):
        v("recettes", f"carte_{i}", "card", {"Values": [mfield(name)]}, label, 245 + i*340, 15, 320, 100)
    v("recettes", "courbe_recettes", "lineChart", {"Category": [field("dim_Mois", "Date")], "Y": [mfield("Recettes MDT")]}, "Evolution mensuelle des recettes (MDT)", 20, 135, 780, 325, (field("dim_Mois", "Date"), "Ascending"))
    v("recettes", "courbe_change", "lineChart", {"Category": [field("dim_Mois", "Date")], "Y": [mfield("EUR TND moyen"), mfield("USD TND moyen")]}, "TND pour une unite de devise", 820, 135, 440, 325)
    v("recettes", "table_mois", "tableEx", {"Values": [field("dim_Mois", "Date"), mfield("Recettes MDT"), mfield("EUR TND moyen"), mfield("USD TND moyen"), mfield("Recettes MEUR estimees")]}, "Detail mensuel et conversion indicative", 20, 480, 1240, 295)
    v("marches", "annee_marches", "slicer", {"Values": [field("dim_Annee", "Annee")]}, "Annee (detail 2021-2023)", 20, 15, 230, 100)
    v("marches", "filtre_marche", "slicer", {"Values": [field("dim_Marche", "Marche")]}, "Marche ou groupe", 270, 15, 400, 100)
    v("marches", "arrivees_total", "card", {"Values": [mfield("Arrivees")]}, "Arrivees non-residents", 690, 15, 275, 100)
    v("marches", "nuitees_total", "card", {"Values": [mfield("Nuitees")]}, "Nuitees, residents inclus", 985, 15, 275, 100)
    v("marches", "barre_arrivees", "clusteredBarChart", {"Category": [field("dim_Marche", "Marche")], "Y": [mfield("Arrivees")]}, "Arrivees par marche", 20, 135, 700, 370, (mfield("Arrivees"), "Descending"))
    v("marches", "saisons", "clusteredColumnChart", {"Category": [field("dim_Saison", "Saison")], "Y": [mfield("Arrivees par saison")]}, "Haute/moyenne et basse saison", 740, 135, 520, 370)
    v("marches", "table_parts", "tableEx", {"Values": [field("dim_Marche", "Marche"), mfield("Arrivees"), mfield("Part du marche %"), mfield("Nuitees")]}, "Volumes et parts dans le total national", 20, 525, 1240, 250)
    v("hebergement", "filtre_region", "slicer", {"Values": [field("dim_Region", "Region")]}, "Region", 20, 15, 290, 100)
    v("hebergement", "filtre_categorie", "slicer", {"Values": [field("dim_Categorie", "Categorie")]}, "Categorie", 330, 15, 290, 100)
    for i, measure in enumerate(["Lits", "Etablissements", "Occupation nationale publiee %"]):
        v("hebergement", f"kpi_offre_{i}", "card", {"Values": [mfield(measure)]}, measure, 640+i*210, 15, 200, 100)
    v("hebergement", "lits_region", "clusteredBarChart", {"Category": [field("dim_Region", "Region", active=True), field("dim_Categorie", "Categorie", active=False)], "Y": [mfield("Lits")]}, "Lits par region puis categorie (exploration)", 20, 135, 600, 640, (mfield("Lits"), "Descending"))
    v("hebergement", "taux_detail", "tableEx", {"Values": [field("dim_Region", "Region"), field("dim_Categorie", "Categorie"), mfield("Lits"), mfield("Taux occupation detail %")]}, "Taux detailles, sans moyenne non ponderee", 640, 135, 620, 640)
    v("territoires", "annee_sites", "slicer", {"Values": [field("dim_Annee", "Annee")]}, "Annee (sites 2019-2023, investissements 2023)", 20, 15, 430, 100)
    v("territoires", "invest_total", "card", {"Values": [mfield("Investissements MDT")]}, "Investissements (MDT)", 470, 15, 380, 100)
    v("territoires", "visiteurs_total", "card", {"Values": [mfield("Visiteurs sites")]}, "Visiteurs des sites et musees", 870, 15, 390, 100)
    v("territoires", "invest_gouv", "clusteredBarChart", {"Category": [field("dim_Gouvernorat", "Gouvernorat")], "Y": [mfield("Investissements MDT")]}, "Investissements par gouvernorat", 20, 135, 600, 640)
    v("territoires", "sites", "clusteredBarChart", {"Category": [field("dim_Site", "Site")], "Y": [mfield("Visiteurs sites")]}, "Visiteurs par site", 640, 135, 620, 640)
    v("previsions", "table_previsions", "tableEx", {"Values": [field("dim_Mois", "Date"), field("fact_previsions", "Modele"), field("fact_previsions", "Cible"), mfield("Previsions MDT")]}, "Semaine 5 : table vide, aucune prevision encore produite", 20, 30, 1240, 730)
    dax = "// Mesures situees dans fact_recettes. Copier une mesure a la fois si necessaire.\n\n"
    dax += "\n\n".join(f"{name} =\n{expression}" for name, (expression, _) in MEASURES.items())
    (destination / "mesures.dax").write_text(dax + "\n", encoding="utf-8")
    (destination / "parametre_RootPath.txt").write_text(csv_path + "\n", encoding="utf-8")
    return {"tables": len(tables), "relationships": len(relationships), "measures": len(MEASURES), "pages": len(pages)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--portable-example", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.destination, args.output_dir, args.portable_example), indent=2))
