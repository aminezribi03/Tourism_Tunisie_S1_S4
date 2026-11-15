"""Petites fonctions de nettoyage, faciles a lire et a tester."""
import math
import re
import unicodedata

import pandas as pd
from lxml import html

from tourism.config import MONTHS


def text(value):
    """Meme cle pour Francais/FRANÇAIS, espaces et underscores."""
    if pd.isna(value):
        return ""
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"[_\-/'’]+", " ", value.upper())
    return " ".join(value.split())


def number(value):
    """Un vide reste None. Une virgule decimale devient un point."""
    if pd.isna(value) or str(value).strip() in {"", "-", "#", "...", "n.d."}:
        return None
    if isinstance(value, str):
        value = value.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Nombre non fini : {value!r}")
    return result


def region(value):
    key = text(value)
    return {
        "TUNIS COTES DE CART HAGE": "TUNIS COTES CARTHAGE",
        "TUNIS COTES DE CARTHAGE": "TUNIS COTES CARTHAGE",
        "JERBA": "DJERBA",
        "KEF": "LE KEF",
    }.get(key, key)


def market(value):
    key = text(value)
    return {"LITUANES": "LITUANIENS", "TOTAL RESIDENTS": "RESIDENTS EN TUNISIE"}.get(key, key)


def category(value):
    raw = str(value).strip()
    if raw and set(raw) == {"*"}:
        return f"{len(raw)} ETOILES"
    key = text(value)
    return {
        "1 ETOILE": "1 ETOILES", "VILLAGES DE VACANCES": "VILLAGES VACANCES",
        "CHAMBRES D HOTES": "CHAMBRES HOTES", "PENSIONS DE FAMILLES": "PENSIONS FAMILLE",
        "HOTELS DE CHARME": "HOTELS CHARME",
    }.get(key, key)


def is_total(value):
    key = text(value)
    return key.startswith("TOTAL") or key.startswith("MOYENNE") or key == "%"


def month_key(year, month_name):
    key = text(month_name)
    if key not in MONTHS:
        raise ValueError(f"Mois inconnu : {month_name!r}")
    return int(year) * 100 + MONTHS[key]


def parse_bct(path):
    """Le .xls BCT est du HTML imbrique. Lire les cellules, pas l'extension.

    read_html() sans decimal=',' transforme parfois 2,0445 en 20445.
    Ici la valeur originale de chaque cellule est convertie explicitement.
    """
    raw = path.read_text(encoding="utf-8-sig")
    root = html.fromstring(raw)
    dates = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", raw)
    dates = list(dict.fromkeys(dates))
    candidates = []
    for table in root.xpath("//table"):
        rows = table.xpath("./tr | ./tbody/tr | ./thead/tr")
        if not rows:
            continue
        header = " ".join(rows[0].itertext()).upper()
        if "USD" not in header or "EUR" not in header:
            continue
        # Une table feuille contient les deux devises, une ligne par mois.
        if table.xpath(".//table"):
            continue
        header_cells = [" ".join(c.itertext()).upper() for c in rows[0].xpath("./td|./th")]
        usd_col = next(i for i, c in enumerate(header_cells) if "USD" in c)
        eur_col = next(i for i, c in enumerate(header_cells) if "EUR" in c)
        values = []
        for row in rows[1:]:
            cells = [" ".join(c.itertext()).strip() for c in row.xpath("./td|./th")]
            if not any(cells):
                continue
            if len(cells) != 2:
                raise ValueError("BCT : ligne avec un nombre inattendu de cellules")
            usd, eur = number(cells[usd_col]), number(cells[eur_col])
            if usd is None and eur is None:
                continue
            if usd is None or eur is None or usd <= 0 or eur <= 0:
                raise ValueError("BCT : taux manquant ou non positif")
            values.append((usd, eur))
        candidates.append(values)
    if len(candidates) != 1 or len(dates) != len(candidates[0]):
        raise ValueError(f"BCT : dates/taux non alignes ({len(dates)} dates, {len(candidates)} tables)")
    result = []
    for date, (usd, eur) in zip(dates, candidates[0], strict=True):
        stamp = pd.to_datetime(date, format="%d/%m/%Y")
        result.append({"MoisKey": stamp.year * 100 + stamp.month,
                       "USD_TND": usd, "EUR_TND": eur})
    frame = pd.DataFrame(result).sort_values("MoisKey").reset_index(drop=True)
    if frame.MoisKey.duplicated().any():
        raise ValueError("BCT : plusieurs taux pour le meme mois")
    return frame
