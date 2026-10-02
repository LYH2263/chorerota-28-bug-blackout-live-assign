import os
import pytest

from app import seed
from app.db import connect, db_path


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """每个用例一个独立 DATA_DIR，建干净库。"""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert str(db_path().parent) == str(tmp_path)
    seed.init_db()
    yield tmp_path


@pytest.fixture()
def c(tmp_db):
    conn = connect()
    yield conn
    conn.close()
