#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "Usage: build_ingestion_image.sh <image-tag>" >&2
  exit 2
fi

image_tag="$1"
script_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${script_directory}/../../.." && pwd)"
api_directory="${repository_root}/services/api"

docker buildx build \
  --platform linux/arm64 \
  --provenance=false \
  --load \
  --file "${api_directory}/Dockerfile.ingestion" \
  --tag "${image_tag}" \
  "${api_directory}"
