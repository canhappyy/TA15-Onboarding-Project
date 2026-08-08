#!/usr/bin/env bash
set -euo pipefail

script_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${script_directory}/../../.." && pwd)"

usage() {
  echo "Usage: manage_lambda_images.sh build|verify <function> <image-reference> | publish-all" >&2
  exit 2
}

configure_function() {
  local function_name="$1"
  case "${function_name}" in
    ingestion)
      dockerfile="${repository_root}/services/api/src/functions/ingestion/Dockerfile"
      build_context="${repository_root}/services/api"
      smoke_code='import importlib.util; import pandas; import numpy; import psycopg; import boto3; assert importlib.util.find_spec("sqlalchemy") is None; from src.functions.ingestion.handler import lambda_handler; service=type("FakeService", (), {"run": lambda self, mode: {"mode": mode, "datasets": {}}})(); modes=("bootstrap", "minute", "hourly", "static"); assert all(lambda_handler({"mode": mode}, None, service=service)["mode"] == mode for mode in modes)'
      ;;
    database_migration)
      dockerfile="${repository_root}/services/api/src/functions/database_migration/Dockerfile"
      build_context="${repository_root}"
      smoke_code='import importlib.util; import psycopg; assert importlib.util.find_spec("pandas") is None; assert importlib.util.find_spec("sqlalchemy") is None; from src.functions.database_migration.handler import lambda_handler, load_migrations; assert callable(lambda_handler); assert load_migrations("/var/task/migrations")'
      ;;
    rds_connectivity)
      dockerfile="${repository_root}/services/api/src/functions/rds_connectivity/Dockerfile"
      build_context="${repository_root}"
      smoke_code='import importlib.util; import psycopg; assert importlib.util.find_spec("pandas") is None; assert importlib.util.find_spec("sqlalchemy") is None; from src.functions.rds_connectivity.handler import lambda_handler; assert callable(lambda_handler)'
      ;;
    *)
      echo "unsupported Lambda function: ${function_name}" >&2
      exit 2
      ;;
  esac
}

build_image() {
  local function_name="$1"
  local image_reference="$2"
  local output_mode="$3"
  configure_function "${function_name}"

  docker buildx build \
    --platform linux/arm64 \
    --provenance=false \
    "${output_mode}" \
    --file "${dockerfile}" \
    --tag "${image_reference}" \
    "${build_context}"
}

verify_image() {
  local function_name="$1"
  local image_reference="$2"
  configure_function "${function_name}"

  local architecture
  architecture="$(docker image inspect --format '{{.Architecture}}' "${image_reference}")"
  if [[ "${architecture}" != "arm64" ]]; then
    echo "expected arm64 image, found ${architecture}" >&2
    return 1
  fi

  docker run --rm \
    --platform linux/arm64 \
    --entrypoint python \
    "${image_reference}" \
    -c "${smoke_code}"
}

image_exists() {
  local repository_url="$1"
  local image_tag="$2"
  local repository_name="${repository_url#*/}"
  local output

  if output="$(aws ecr describe-images \
    --region "${AWS_REGION}" \
    --repository-name "${repository_name}" \
    --image-ids "imageTag=${image_tag}" 2>&1)"; then
    return 0
  fi
  if [[ "${output}" == *"ImageNotFoundException"* ]]; then
    return 1
  fi
  echo "${output}" >&2
  return 2
}

publish_all() {
  local required_variables=(
    AWS_REGION
    INGESTION_REPOSITORY_URL
    INGESTION_IMAGE_TAG
    DATABASE_MIGRATION_REPOSITORY_URL
    DATABASE_MIGRATION_IMAGE_TAG
    RDS_CONNECTIVITY_REPOSITORY_URL
    RDS_CONNECTIVITY_IMAGE_TAG
  )
  local variable_name
  for variable_name in "${required_variables[@]}"; do
    if [[ -z "${!variable_name:-}" ]]; then
      echo "missing required environment variable: ${variable_name}" >&2
      exit 2
    fi
  done

  local registry="${INGESTION_REPOSITORY_URL%%/*}"
  if [[ "${DATABASE_MIGRATION_REPOSITORY_URL%%/*}" != "${registry}" ||
    "${RDS_CONNECTIVITY_REPOSITORY_URL%%/*}" != "${registry}" ]]; then
    echo "Lambda image repositories must use the same ECR registry" >&2
    exit 2
  fi

  local functions=(ingestion database_migration rds_connectivity)
  local repository_urls=(
    "${INGESTION_REPOSITORY_URL}"
    "${DATABASE_MIGRATION_REPOSITORY_URL}"
    "${RDS_CONNECTIVITY_REPOSITORY_URL}"
  )
  local image_tags=(
    "${INGESTION_IMAGE_TAG}"
    "${DATABASE_MIGRATION_IMAGE_TAG}"
    "${RDS_CONNECTIVITY_IMAGE_TAG}"
  )
  local missing=(false false false)
  local index status

  for index in 0 1 2; do
    if image_exists "${repository_urls[index]}" "${image_tags[index]}"; then
      continue
    else
      status=$?
      if [[ "${status}" -eq 1 ]]; then
        missing[index]=true
      else
        exit "${status}"
      fi
    fi
  done

  if [[ "${missing[*]}" == *true* ]]; then
    aws ecr get-login-password --region "${AWS_REGION}" |
      docker login --username AWS --password-stdin "${registry}"
  fi

  for index in 0 1 2; do
    if [[ "${missing[index]}" == true ]]; then
      build_image \
        "${functions[index]}" \
        "${repository_urls[index]}:${image_tags[index]}" \
        --push
    fi
  done
}

mode="${1:-}"
case "${mode}" in
  build)
    [[ "$#" -eq 3 ]] || usage
    build_image "$2" "$3" --load
    ;;
  verify)
    [[ "$#" -eq 3 ]] || usage
    verify_image "$2" "$3"
    ;;
  publish-all)
    [[ "$#" -eq 1 ]] || usage
    publish_all
    ;;
  *)
    usage
    ;;
esac
