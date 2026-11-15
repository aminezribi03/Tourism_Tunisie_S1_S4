"""Tous les chemins sont calcules depuis le projet, jamais depuis le PC de l'auteur."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUTPUT = Path(os.environ.get("TOURISM_OUTPUT_DIR", ROOT / "outputs")).resolve()
DB = OUTPUT / "tourisme.sqlite"
TOURISM_FILE = "pwer bi base de donnes.xlsx"
BCT_RAW_FILE = "BCT_statistque.xls"
BCT_CHECK_FILE = "Source2_BCT_change.xlsx"
SNAPSHOT_YEAR = 2023  # Annee du rapport ONTT. Ce n'est pas une serie historique.
MONTHS = {
    "JANVIER": 1, "FEVRIER": 2, "MARS": 3, "AVRIL": 4,
    "MAI": 5, "JUIN": 6, "JUILLET": 7, "AOUT": 8,
    "SEPTEMBRE": 9, "OCTOBRE": 10, "NOVEMBRE": 11, "DECEMBRE": 12,
}

ONTT_URL = "https://www.ontt.tn/sites/default/files/inline-files/EXTRAIT%202023%20.pdf"
BCT_URL = "https://www.bct.gov.tn/bct/siteprod/tableau_statistique.jsp?params=PL213010"
