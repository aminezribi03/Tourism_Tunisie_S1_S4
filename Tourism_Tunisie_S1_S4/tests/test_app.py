from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tourism.config import ROOT


@pytest.fixture
def app():
    result = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not result.exception
    return result


@pytest.mark.parametrize("page", ["Vue d'ensemble", "Recettes et change", "Marches et saisons", "Hebergement", "Investissements et patrimoine", "Qualite et donnees", "Power BI", "Previsions (S5)"])
def test_all_pages_render_without_exception(app, page):
    app.radio(key="nav").set_value(page).run()
    assert not app.exception
    assert not app.error


def test_filters_and_empty_selection(app):
    app.selectbox(key="overview_year").set_value(2019).run()
    assert not app.exception
    assert app.metric[1].value == "n.d."
    app.radio(key="nav").set_value("Recettes et change").run()
    app.multiselect(key="revenue_years").set_value([]).run()
    assert not app.exception
    assert any("au moins une annee" in x.value for x in app.info)
    app.multiselect(key="revenue_years").set_value([2023]).run()
    app.selectbox(key="currency").set_value("MEUR (estimation)").run()
    assert not app.exception
    assert len(app.metric) == 3


def test_hotel_region_filter_changes_capacity(app):
    app.radio(key="nav").set_value("Hebergement").run()
    total = app.metric[0].value
    app.multiselect(key="hotel_regions").set_value(["SOUSSE"]).run()
    assert not app.exception
    assert app.metric[0].value != total


def test_forecast_page_shows_no_invented_prediction(app):
    app.radio(key="nav").set_value("Previsions (S5)").run()
    assert not app.exception
    assert any("Aucune prevision" in x.value for x in app.info)
