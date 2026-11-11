"""Shared fixtures. The repository root is put on sys.path so the packages import without installing."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from generator.writer import write_all  # noqa: E402
from sql.loader import build_database  # noqa: E402


@pytest.fixture(scope="session")
def generated_dir(tmp_path_factory):
    """The full default data set, generated once per test session."""
    out = tmp_path_factory.mktemp("generated")
    write_all(out)
    return out


@pytest.fixture(scope="session")
def generated_db(generated_dir, tmp_path_factory):
    """The default data set loaded into SQLite, with every view created."""
    db = tmp_path_factory.mktemp("db") / "service.db"
    conn = build_database(generated_dir, db)
    yield conn
    conn.close()
