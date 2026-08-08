import json
import sys
from pathlib import Path

import pytest


PIPELINE_DIR = Path(__file__).resolve().parents[2] / "src" / "pipeline"
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "pipeline"

if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))


class FakeResult:
    def __init__(self, rows=()):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)


class FakeConnection:
    def __init__(self, select_rows=()):
        self.select_rows = list(select_rows)
        self.statements = []

    def execute(self, statement, parameters=None):
        sql = str(statement)
        self.statements.append((sql, parameters))
        if "SELECT location_id FROM sensor_location" in sql:
            return FakeResult(self.select_rows)
        return FakeResult()


class FakeContext:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *_args):
        return False


class FakeEngine:
    def __init__(self, select_rows=()):
        self.connection = FakeConnection(select_rows)

    def connect(self):
        return FakeContext(self.connection)

    def begin(self):
        return FakeContext(self.connection)


@pytest.fixture
def pipeline_fixture_dir():
    return FIXTURE_DIR


@pytest.fixture
def pipeline_expectations(pipeline_fixture_dir):
    return json.loads((pipeline_fixture_dir / "expectations.json").read_text())


@pytest.fixture
def capture_to_sql(monkeypatch):
    writes = []

    def capture(frame, name, _connection, **options):
        writes.append({"table": name, "frame": frame.copy(), "options": options})

    monkeypatch.setattr("pandas.DataFrame.to_sql", capture)
    return writes
