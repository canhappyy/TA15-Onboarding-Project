#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "Usage: verify_ingestion_image.sh <image-tag>" >&2
  exit 2
fi

image_tag="$1"
architecture="$(docker image inspect --format '{{.Architecture}}' "${image_tag}")"

if [[ "${architecture}" != "arm64" ]]; then
  echo "expected arm64 image, found ${architecture}" >&2
  exit 1
fi

smoke_code='import importlib.util; import pandas; import numpy; import psycopg; import boto3; assert importlib.util.find_spec("sqlalchemy") is None; from src.functions.ingestion.handler import lambda_handler; service=type("FakeService", (), {"run": lambda self, mode: {"mode": mode, "datasets": {}}})(); modes=("bootstrap", "minute", "hourly", "static"); assert all(lambda_handler({"mode": mode}, None, service=service)["mode"] == mode for mode in modes)'

docker run \
  --rm \
  --platform linux/arm64 \
  --entrypoint python \
  "${image_tag}" \
  -c "${smoke_code}"
