import os
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPOSITORY_ROOT / "infra" / "aws" / "scripts" / "manage_lambda_images.sh"


def _fake_docker(tmp_path: Path, *, architecture: str = "arm64") -> Path:
    executable = tmp_path / "docker"
    executable.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%s\\n' \"$*\" >> \"$DOCKER_LOG\"\n"
        "if [[ \"${1:-}\" == image && \"${2:-}\" == inspect ]]; then\n"
        f"  printf '{architecture}\\n'\n"
        "fi\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _environment(tmp_path: Path, *, architecture: str = "arm64"):
    _fake_docker(tmp_path, architecture=architecture)
    log_path = tmp_path / "docker.log"
    return {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "DOCKER_LOG": str(log_path),
    }, log_path


def _run(args: list[str], environment: dict[str, str]):
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_build_maps_each_function_to_local_dockerfile_and_arm64_context(tmp_path):
    expected = {
        "ingestion": ("src/functions/ingestion/Dockerfile", "/services/api"),
        "database_migration": (
            "src/functions/database_migration/Dockerfile",
            str(REPOSITORY_ROOT),
        ),
        "rds_connectivity": (
            "src/functions/rds_connectivity/Dockerfile",
            str(REPOSITORY_ROOT),
        ),
    }

    for function_name, (dockerfile, context) in expected.items():
        function_dir = tmp_path / function_name
        function_dir.mkdir()
        environment, log_path = _environment(function_dir)

        result = _run(
            ["build", function_name, f"clearway-{function_name}:test"], environment
        )

        assert result.returncode == 0, result.stderr
        invocation = log_path.read_text(encoding="utf-8").strip()
        assert invocation.startswith("buildx build ")
        assert "--platform linux/arm64" in invocation
        assert "--provenance=false" in invocation
        assert "--load" in invocation
        assert dockerfile in invocation
        assert invocation.endswith(context)


def test_verify_runs_function_specific_smoke_commands(tmp_path):
    expected_fragments = {
        "ingestion": ("import pandas", "src.functions.ingestion.handler", '"status"'),
        "database_migration": ("load_migrations", "/var/task/migrations"),
        "rds_connectivity": ("import psycopg", "src.functions.rds_connectivity.handler"),
    }

    for function_name, fragments in expected_fragments.items():
        function_dir = tmp_path / function_name
        function_dir.mkdir()
        environment, log_path = _environment(function_dir)

        result = _run(
            ["verify", function_name, f"clearway-{function_name}:test"], environment
        )

        assert result.returncode == 0, result.stderr
        invocation = next(
            line
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("run ")
        )
        assert "--platform linux/arm64" in invocation
        assert "--entrypoint python" in invocation
        assert all(fragment in invocation for fragment in fragments)


def test_verify_rejects_non_arm64_image(tmp_path):
    environment, _ = _environment(tmp_path, architecture="amd64")

    result = _run(["verify", "ingestion", "clearway-ingestion:test"], environment)

    assert result.returncode == 1
    assert "expected arm64 image" in result.stderr


def test_unknown_mode_or_function_fails_before_docker(tmp_path):
    environment, log_path = _environment(tmp_path)

    unknown_mode = _run(["ship", "ingestion", "image:test"], environment)
    unknown_function = _run(["build", "health", "image:test"], environment)

    assert unknown_mode.returncode == 2
    assert unknown_function.returncode == 2
    assert not log_path.exists()


def _publish_environment(tmp_path: Path):
    environment, docker_log = _environment(tmp_path)
    environment.update(
        {
            "AWS_REGION": "ap-southeast-4",
            "INGESTION_REPOSITORY_URL": "123.dkr.ecr.ap-southeast-4.amazonaws.com/ingestion",
            "INGESTION_IMAGE_TAG": "sha-ingestion",
            "DATABASE_MIGRATION_REPOSITORY_URL": "123.dkr.ecr.ap-southeast-4.amazonaws.com/migration",
            "DATABASE_MIGRATION_IMAGE_TAG": "sha-migration",
            "RDS_CONNECTIVITY_REPOSITORY_URL": "123.dkr.ecr.ap-southeast-4.amazonaws.com/connectivity",
            "RDS_CONNECTIVITY_IMAGE_TAG": "sha-connectivity",
        }
    )
    return environment, docker_log


def test_publish_all_pushes_three_missing_content_tags(tmp_path):
    environment, docker_log = _publish_environment(tmp_path)
    aws_log = tmp_path / "aws.log"
    aws = tmp_path / "aws"
    aws.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%s\\n' \"$*\" >> \"$AWS_LOG\"\n"
        "if [[ \"${1:-}\" == ecr && \"${2:-}\" == describe-images ]]; then\n"
        "  printf 'ImageNotFoundException\\n' >&2\n"
        "  exit 1\n"
        "fi\n"
        "if [[ \"${1:-}\" == ecr && \"${2:-}\" == get-login-password ]]; then\n"
        "  printf 'temporary-password\\n'\n"
        "fi\n",
        encoding="utf-8",
    )
    aws.chmod(0o755)
    environment["AWS_LOG"] = str(aws_log)

    result = _run(["publish-all"], environment)

    assert result.returncode == 0, result.stderr
    assert sum(
        "describe-images" in line
        for line in aws_log.read_text(encoding="utf-8").splitlines()
    ) == 3
    invocations = docker_log.read_text(encoding="utf-8").splitlines()
    builds = [line for line in invocations if line.startswith("buildx build ")]
    assert len(builds) == 3
    assert all("--push" in line and "--platform linux/arm64" in line for line in builds)
    assert any("ingestion:sha-ingestion" in line for line in builds)
    assert any("migration:sha-migration" in line for line in builds)
    assert any("connectivity:sha-connectivity" in line for line in builds)


def test_publish_all_skips_existing_tags_without_docker(tmp_path):
    environment, docker_log = _publish_environment(tmp_path)
    aws = tmp_path / "aws"
    aws.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    aws.chmod(0o755)

    result = _run(["publish-all"], environment)

    assert result.returncode == 0, result.stderr
    assert not docker_log.exists()


def test_publish_all_stops_on_ecr_auth_error(tmp_path):
    environment, docker_log = _publish_environment(tmp_path)
    aws = tmp_path / "aws"
    aws.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'AccessDeniedException: denied\\n' >&2\n"
        "exit 254\n",
        encoding="utf-8",
    )
    aws.chmod(0o755)

    result = _run(["publish-all"], environment)

    assert result.returncode != 0
    assert "AccessDeniedException" in result.stderr
    assert not docker_log.exists()
