import hashlib
import json
import shutil
import sqlite3

import pandas as pd
import pytest

from tourism import analytics as a
from tourism.cleaning import category, month_key, number, parse_bct, region
from tourism.config import BCT_CHECK_FILE, BCT_RAW_FILE, RAW, TOURISM_FILE
from tourism.etl import Builder, run_pipeline


def test_bct_decimal_and_complete_months():
    raw = parse_bct(RAW / BCT_RAW_FILE)
    assert len(raw) == 96
    assert raw.iloc[0].USD_TND == pytest.approx(2.0445)
    assert raw.iloc[0].EUR_TND == pytest.approx(2.2193)
    assert raw.MoisKey.min() == 201601
    assert raw.MoisKey.max() == 202312
    prepared = pd.read_excel(RAW / BCT_CHECK_FILE)
    assert raw.EUR_TND.tolist() == pytest.approx(prepared.EUR_TND_moyen.tolist())
    assert raw.USD_TND.tolist() == pytest.approx(prepared.USD_TND_moyen.tolist())


def test_normalization_and_missing_values():
    assert number(None) is None
    assert number("-") is None
    assert number("0") == 0
    assert number("2,0445") == pytest.approx(2.0445)
    assert region("TUNIS-CÔTES DE CART- HAGE") == region("Tunis_Cotes_Carthage")
    assert category("*****") == category("5_etoiles")
    assert category("PENSIONS DE FAMILLES") == category("Pensions_famille")
    assert month_key(2023, "août") == 202308
    with pytest.raises(ValueError):
        month_key(2023, "MOIS INCONNU")


def test_no_forecast_and_enforced_foreign_keys(con):
    assert con.execute("SELECT COUNT(*) FROM fact_previsions").fetchone()[0] == 0
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO fact_recettes (MoisKey,Recettes_MDT,SourceKey,SourceFeuille,SourceLigne) VALUES (209901,10,1,'test',1)")


def test_national_figures_without_double_counting(con):
    cases = [
        ("SELECT SUM(Recettes_MDT) FROM fact_recettes WHERE MoisKey BETWEEN 202301 AND 202312", 6920.6),
        ("SELECT SUM(Arrivees) FROM fact_arrivees WHERE AnneeKey=2023", 9370511),
        ("SELECT SUM(Nuitees) FROM fact_nuitees WHERE AnneeKey=2023", 25351033),
        ("SELECT SUM(Lits) FROM fact_capacite", 230726),
        ("SELECT SUM(Etablissements) FROM fact_capacite", 905),
        ("SELECT SUM(Total_kTND)/1000 FROM fact_investissements", 149.643),
    ]
    for query, expected in cases:
        assert con.execute(query).fetchone()[0] == pytest.approx(expected)


def test_source_totals_and_percentages_excluded(con):
    rows = con.execute("SELECT Marche FROM vw_arrivees").fetchall()
    assert not any(r[0].startswith("TOTAL") or r[0] == "%" for r in rows)
    assert "MOYENS ORIENTAUX" not in {r[0] for r in rows}
    assert con.execute("SELECT COUNT(*) FROM vw_nuitees WHERE Marche='RESIDENTS EN TUNISIE'").fetchone()[0] == 3


def test_grains_unique_and_lineage_exists(con, warehouse):
    grains = json.loads((warehouse[0] / "grains.json").read_text())
    for table, columns in grains.items():
        group = ",".join(columns)
        assert con.execute(f"SELECT {group},COUNT(*) FROM {table} GROUP BY {group} HAVING COUNT(*)>1").fetchall() == []
        assert con.execute(f"SELECT COUNT(*) FROM {table} WHERE SourceKey IS NULL OR SourceLigne IS NULL OR SourceFeuille IS NULL").fetchone()[0] == 0


def test_occupancy_joins_capacity_and_invalid_value_is_null(con, warehouse):
    assert con.execute("SELECT COUNT(*) FROM fact_occupation o LEFT JOIN fact_capacite c USING(AnneeKey,RegionKey,CategorieKey) WHERE c.ObservationKey IS NULL").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM fact_occupation WHERE Taux_pct>100 OR Taux_pct<0").fetchone()[0] == 0
    invalid = con.execute("SELECT Taux_pct FROM vw_occupation WHERE Region='DJERBA ZARZIS' AND Categorie='VILLAGES VACANCES'").fetchone()
    assert invalid == (None,)
    audit = pd.read_csv(warehouse[0] / "audit_lignes.csv")
    assert audit.Motif.str.contains("hors de 0 a 100").sum() == 1
    assert len(audit[audit.Feuille.eq("Duree_Region")]) == 38


def test_exports_and_monthly_join_do_not_multiply_revenue(con, warehouse):
    flat = pd.read_csv(warehouse[0] / "powerbi_csv" / "vw_recettes_change.csv")
    assert len(flat) == 96
    assert flat.MoisKey.is_unique
    assert flat.loc[flat.Annee.eq(2023), "Recettes_MDT"].sum() == pytest.approx(6920.6)
    first = flat.iloc[0]
    assert first.Recettes_MEUR_estimees == pytest.approx(first.Recettes_MDT / first.EUR_TND)
    assert flat.EUR_TND.gt(0).all()


def test_analytics_year_and_no_data(warehouse):
    db = warehouse[0] / "tourisme.sqlite"
    kpi = a.summary(2023, db)
    assert kpi["recettes"] == pytest.approx(6920.6)
    assert kpi["arrivees"] == 9370511
    assert kpi["recettes_yoy"] == pytest.approx((6920.6/5420.1-1)*100)
    assert a.summary(2019, db)["arrivees"] is None
    assert a.safe_sum(pd.Series([], dtype=float)) is None
    assert a.yoy(0, 10) == -100
    assert a.yoy(10, 0) is None
    with pytest.raises(ValueError):
        a.read_table("dim_Source; DROP TABLE fact_recettes", db)


def test_rebuild_is_idempotent_and_keeps_input_bytes(tmp_path):
    originals = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.iterdir() if p.is_file()}
    first = run_pipeline(RAW, tmp_path)
    csv_before = (tmp_path / "powerbi_csv" / "fact_recettes.csv").read_bytes()
    second = run_pipeline(RAW, tmp_path)
    assert first["observations"] == second["observations"]
    assert csv_before == (tmp_path / "powerbi_csv" / "fact_recettes.csv").read_bytes()
    assert originals == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.iterdir() if p.is_file()}


def test_duplicate_business_key_rejected(tmp_path):
    builder = Builder(RAW, tmp_path)
    builder.monthly()
    builder.nationalities()
    builder.supply()
    builder.other()
    builder.tables["fact_recettes"].append(builder.tables["fact_recettes"][0].copy())
    with pytest.raises(ValueError, match="cle metier dupliquee"):
        builder.validate_records()


def test_bad_bct_does_not_overwrite_existing_db(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    for name in [TOURISM_FILE, BCT_RAW_FILE, BCT_CHECK_FILE]:
        shutil.copy2(RAW / name, raw / name)
    output = tmp_path / "outputs"
    output.mkdir()
    old = output / "tourisme.sqlite"
    old.write_bytes(b"previous database placeholder")
    bad = (raw / BCT_RAW_FILE).read_text(encoding="utf-8").replace("2,0445", "-2,0445", 1)
    (raw / BCT_RAW_FILE).write_text(bad, encoding="utf-8")
    with pytest.raises(ValueError, match="non positif"):
        run_pipeline(raw, output)
    assert old.read_bytes() == b"previous database placeholder"


def test_controls_all_pass(warehouse):
    report = warehouse[1]
    assert report["statut"] == "OK"
    assert all(c["Statut"] == "OK" for c in report["controles"])
    assert report["observations"]["fact_recettes"] == 96
