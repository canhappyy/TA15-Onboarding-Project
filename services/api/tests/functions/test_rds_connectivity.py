import json
import os
import unittest
from unittest.mock import patch

from src.functions.rds_connectivity.handler import (
    DatabaseConnectionSettings,
    DatabaseCredentials,
    PsycopgDatabaseProbe,
    SecretsManagerSecretReader,
    lambda_handler,
)


class FakeSecretReader:
    def __init__(self, credentials):
        self.credentials = credentials
        self.requested_arn = None

    def get_database_credentials(self, secret_arn):
        self.requested_arn = secret_arn
        return self.credentials


class FakeDatabaseProbe:
    def __init__(self, error=None):
        self.error = error
        self.settings = None

    def check(self, settings):
        self.settings = settings
        if self.error:
            raise self.error


class FakeSecretsManagerClient:
    def __init__(self, payload):
        self.payload = payload
        self.requested_secret_id = None

    def get_secret_value(self, SecretId):
        self.requested_secret_id = SecretId
        return {"SecretString": json.dumps(self.payload)}


class FakeCursor:
    def __init__(self, result=(1,)):
        self.result = result
        self.statement = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement):
        self.statement = statement

    def fetchone(self):
        return self.result


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self):
        return self.fake_cursor


class RdsConnectivityTests(unittest.TestCase):
    def setUp(self):
        self.credentials = DatabaseCredentials(
            username="clearway_admin",
            password="super-secret",
        )
        self.settings = DatabaseConnectionSettings(
            host="private.example.internal",
            port=5432,
            dbname="clearway",
            username="clearway_admin",
            password="super-secret",
        )

    def test_handler_reads_configured_secret_and_checks_database(self):
        secret_reader = FakeSecretReader(self.credentials)
        database_probe = FakeDatabaseProbe()

        environment = {
            "DATABASE_HOST": "private.example.internal",
            "DATABASE_PORT": "5432",
            "DATABASE_NAME": "clearway",
            "DATABASE_SECRET_ARN": "arn:aws:secretsmanager:mock",
        }
        with patch.dict(os.environ, environment, clear=True):
            result = lambda_handler(
                {},
                None,
                secret_reader=secret_reader,
                database_probe=database_probe,
            )

        self.assertEqual({"status": "ok"}, result)
        self.assertEqual("arn:aws:secretsmanager:mock", secret_reader.requested_arn)
        self.assertEqual(self.settings, database_probe.settings)

    def test_secret_reader_accepts_rds_managed_secret_without_database_metadata(self):
        client = FakeSecretsManagerClient(
            {
                "username": "clearway_admin",
                "password": "super-secret",
            }
        )

        credentials = SecretsManagerSecretReader(client=client).get_database_credentials("secret-arn")

        self.assertEqual(self.credentials, credentials)
        self.assertEqual("secret-arn", client.requested_secret_id)

    def test_secret_reader_rejects_missing_credentials(self):
        client = FakeSecretsManagerClient({"username": "clearway_admin"})

        with self.assertRaisesRegex(ValueError, "missing required credentials"):
            SecretsManagerSecretReader(client=client).get_database_credentials("secret-arn")

    def test_handler_does_not_log_partial_credentials(self):
        client = FakeSecretsManagerClient({"username": "clearway_admin"})
        environment = {
            "DATABASE_HOST": "private.example.internal",
            "DATABASE_PORT": "5432",
            "DATABASE_NAME": "clearway",
            "DATABASE_SECRET_ARN": "arn:aws:secretsmanager:mock",
        }

        with patch.dict(os.environ, environment, clear=True):
            with self.assertLogs("rds_connectivity", level="ERROR") as logs:
                with self.assertRaisesRegex(RuntimeError, "RDS connectivity check failed"):
                    lambda_handler(
                        {},
                        None,
                        secret_reader=SecretsManagerSecretReader(client=client),
                        database_probe=FakeDatabaseProbe(),
                    )

        self.assertNotIn("clearway_admin", " ".join(logs.output))

    def test_database_probe_requires_tls_and_executes_select_one(self):
        cursor = FakeCursor()
        captured = {}

        def connect(**kwargs):
            captured.update(kwargs)
            return FakeConnection(cursor)

        PsycopgDatabaseProbe(connect=connect).check(self.settings)

        self.assertEqual("require", captured["sslmode"])
        self.assertEqual(5, captured["connect_timeout"])
        self.assertEqual("SELECT 1", cursor.statement)

    def test_handler_logs_no_secret_or_connection_details_on_failure(self):
        secret_reader = FakeSecretReader(self.credentials)
        database_probe = FakeDatabaseProbe(ValueError("super-secret private.example.internal"))

        environment = {
            "DATABASE_HOST": "private.example.internal",
            "DATABASE_PORT": "5432",
            "DATABASE_NAME": "clearway",
            "DATABASE_SECRET_ARN": "arn:aws:secretsmanager:mock",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertLogs("rds_connectivity", level="ERROR") as logs:
                with self.assertRaisesRegex(RuntimeError, "RDS connectivity check failed"):
                    lambda_handler(
                        {},
                        None,
                        secret_reader=secret_reader,
                        database_probe=database_probe,
                    )

        output = " ".join(logs.output)
        self.assertNotIn("super-secret", output)
        self.assertNotIn("private.example.internal", output)


if __name__ == "__main__":
    unittest.main()
