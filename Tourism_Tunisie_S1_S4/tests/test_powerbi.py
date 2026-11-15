"""Validation statique PBIR officielle + coherence du modele. Pas d'execution DAX."""
import importlib.util
import json
import re
from pathlib import Path

from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

from tourism.config import ROOT

SCHEMAS = Path(__file__).parent / "schemas"


def test_pbir_definitions_against_official_schemas():
    index = json.loads((SCHEMAS / "index.json").read_text())
    documents = {url: json.loads((SCHEMAS / filename).read_text()) for url, filename in index.items()}
    registry = Registry().with_resources((url, Resource.from_contents(doc, default_specification=DRAFT7)) for url, doc in documents.items())
    checked = 0
    for path in (ROOT / "powerbi").rglob("*"):
        if path.suffix not in {".json", ".pbir", ".pbip", ".pbism"} and path.name != ".platform":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if "$schema" not in data:
            continue
        schema = documents[data["$schema"]]
        errors = list(Draft7Validator(schema, registry=registry).iter_errors(data))
        assert not errors, f"{path}: " + "; ".join(e.message for e in errors)
        checked += 1
    assert checked >= 35


def test_model_relationships_and_visual_references():
    base = ROOT / "powerbi"
    model = json.loads((base / "Tourisme.SemanticModel" / "model.bim").read_text())["model"]
    tables = {t["name"]: t for t in model["tables"]}
    columns = {name: {c["name"] for c in table["columns"]} for name, table in tables.items()}
    measures = {(name, m["name"]) for name, table in tables.items() for m in table.get("measures", [])}
    assert len(measures) == 17
    assert len(tables) == 27
    assert json.loads((base / "Tourisme.Report" / "definition" / "version.json").read_text())["version"] == "2.0.0"
    for folder, kind in [("Tourisme.Report", "Report"), ("Tourisme.SemanticModel", "SemanticModel")]:
        metadata = json.loads((base / folder / ".platform").read_text())
        assert metadata["metadata"]["type"] == kind
    for r in model["relationships"]:
        assert r["fromColumn"] in columns[r["fromTable"]]
        assert r["toColumn"] in columns[r["toTable"]]
        assert r["crossFilteringBehavior"] == "oneDirection"
    # Une seule route annee -> mois -> recettes. Pas de seconde relation annee -> recettes.
    assert not any(r["fromTable"] == "fact_recettes" and r["toTable"] == "dim_Annee" for r in model["relationships"])
    for path in (base / "Tourisme.Report").rglob("visual.json"):
        visual = json.loads(path.read_text())["visual"]
        for role in visual["query"]["queryState"].values():
            for projection in role["projections"]:
                kind = next(iter(projection["field"]))
                expr = projection["field"][kind]
                table = expr["Expression"]["SourceRef"]["Entity"]
                prop = expr["Property"]
                assert table in tables
                assert (table, prop) in measures if kind == "Measure" else prop in columns[table]
    for table in tables.values():
        for measure in table.get("measures", []):
            for referenced_table, col in re.findall(r"\b([A-Za-z_][A-Za-z_0-9]*)\[([^\]]+)\]", "\n".join(measure["expression"])):
                assert col in columns[referenced_table], (measure["name"], referenced_table, col)


def test_powerbi_generator_relocates_paths_and_does_not_change_dwh(tmp_path, warehouse):
    path = ROOT / "scripts" / "configure_powerbi.py"
    spec = importlib.util.spec_from_file_location("configure_powerbi", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.build(tmp_path / "projet avec espaces", warehouse[0])
    assert result == {"tables": 27, "relationships": 45, "measures": 17, "pages": 5}
    model = json.loads((tmp_path / "projet avec espaces" / "Tourisme.SemanticModel" / "model.bim").read_text())
    parameter = model["model"]["expressions"][0]["expression"]
    assert (warehouse[0] / "powerbi_csv").as_posix() in parameter
    assert "IsParameterQuery=true" in parameter
