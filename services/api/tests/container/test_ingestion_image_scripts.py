import os
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
BUILD_SCRIPT = REPOSITORY_ROOT / "infra" / "aws" / "scripts" / "build_ingestion_image.sh"
VERIFY_SCRIPT = REPOSITORY_ROOT / "infra" / "aws" / "scripts" / "verify_ingestion_image.sh"


def _fake_docker(tmp_path):
    executable = tmp_path / "docker"
    executable.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%s\\n' \"$*\" >> \"$DOCKER_LOG\"\n"
        "if [[ \"${1:-}\" == image && \"${2:-}\" == inspect ]]; then\n"
        "  printf 'arm64\\n'\n"
        "fi\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _environment(tmp_path):
    _fake_docker(tmp_path)
    log_path = tmp_path / "docker.log"
    return {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "DOCKER_LOG": str(log_path),
    }, log_path


def test_build_script_builds_loaded_linux_arm64_image_from_api_context(tmp_path):
    environment, log_path = _environment(tmp_path)

    result = subprocess.run(
        ["bash", str(BUILD_SCRIPT), "clearway-ingestion:test"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    invocation = log_path.read_text(encoding="utf-8")
    assert invocation.startswith("buildx build ")
    assert "--platform linux/arm64" in invocation
    assert "--provenance=false" in invocation
    assert "--load" in invocation
    assert "--tag clearway-ingestion:test" in invocation
    assert "--file " in invocation
    assert invocation.rstrip().endswith("/services/api")


def test_verify_script_rejects_non_arm64_image(tmp_path):
    executable = _fake_docker(tmp_path)
    executable.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == image && \"${2:-}\" == inspect ]]; then\n"
        "  printf 'amd64\\n'\n"
        "fi\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
    }

    result = subprocess.run(
        ["bash", str(VERIFY_SCRIPT), "clearway-ingestion:test"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "expected arm64 image" in result.stderr


def test_verify_script_runs_dependency_and_handler_smoke_inside_image(tmp_path):
    environment, log_path = _environment(tmp_path)

    result = subprocess.run(
        ["bash", str(VERIFY_SCRIPT), "clearway-ingestion:test"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    invocations = log_path.read_text(encoding="utf-8").splitlines()
    run_invocation = next(line for line in invocations if line.startswith("run "))
    assert "--platform linux/arm64" in run_invocation
    assert "--entrypoint python" in run_invocation
    assert "clearway-ingestion:test" in run_invocation
    assert "import pandas" in run_invocation
    assert "import psycopg" in run_invocation
    assert 'find_spec("sqlalchemy") is None' in run_invocation
    assert "lambda_handler" in run_invocation
