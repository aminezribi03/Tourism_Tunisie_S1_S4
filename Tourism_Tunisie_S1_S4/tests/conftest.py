import sqlite3
from pathlib import Path

import pytest

from tourism.config import RAW
from tourism.etl import run_pipeline


@pytest.fixture(scope="session")
def warehouse(tmp_path_factory):
    destination = tmp_path_factory.mktemp("tourisme_test")
    report = run_pipeline(RAW, destination)
    return destination, report


@pytest.fixture
def con(warehouse):
    connection = sqlite3.connect(warehouse[0] / "tourisme.sqlite")
    connection.execute("PRAGMA foreign_keys=ON")
    yield connection
    connection.close()
