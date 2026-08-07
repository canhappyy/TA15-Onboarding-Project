#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 2 ]]; then
  echo "Usage: build_psycopg_layer.sh <output-zip> <requirements-file>" >&2
  exit 2
fi

output_zip="$1"
requirements_file="$2"
temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT

mkdir -p "$(dirname "$output_zip")"
output_directory="$(cd "$(dirname "$output_zip")" && pwd)"
output_zip="${output_directory}/$(basename "$output_zip")"

python3 -m pip install \
  --disable-pip-version-check \
  --no-compile \
  --implementation cp \
  --python-version 3.13 \
  --abi cp313 \
  --platform manylinux2014_aarch64 \
  --only-binary=:all: \
  --requirement "$requirements_file" \
  --target "$temporary_directory/python"

(
  cd "$temporary_directory"
  python3 -m zipfile -c "$output_zip" python
)
