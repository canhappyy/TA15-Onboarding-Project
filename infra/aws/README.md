# AWS infrastructure

Terraform deploys the ClearWay AWS resources. Build the Python 3.13 ARM64
`psycopg` layer before planning or applying the RDS connectivity Lambda.

From `infra/aws`:

```bash
bash scripts/build_psycopg_layer.sh \
  .terraform-build/psycopg-layer.zip \
  layers/psycopg/requirements.txt

terraform fmt -check -recursive
terraform validate
terraform test
terraform plan
terraform apply
```

The generated ZIP is ignored by Git. Rebuild it after a clean checkout or
when the requirements, Python runtime, architecture, or build script changes.
`terraform destroy` removes the AWS layer but does not remove the local ZIP.

## Build the ingestion container

The ingestion Lambda uses a separate Python 3.13 ARM64 container containing
pandas, NumPy, psycopg, and boto3. With Docker running, build and verify it from
`infra/aws`:

```bash
bash scripts/build_ingestion_image.sh clearway-ingestion:dev
bash scripts/verify_ingestion_image.sh clearway-ingestion:dev
```

The verification checks the image architecture, imports its runtime
dependencies, and exercises all four ingestion handler modes. Terraform does
not build the image. ECR publishing and Lambda deployment are added by the
ingestion-infrastructure milestone.

Runtime dependencies are declared in `services/api/requirements-ingestion.in`
and hash-locked in `requirements-ingestion.txt`. Regenerate the lock with
Python 3.13 and `pip-tools` whenever a direct dependency changes:

```bash
pip-compile --generate-hashes \
  --output-file=../../services/api/requirements-ingestion.txt \
  ../../services/api/requirements-ingestion.in
```

After deployment, invoke the private connectivity check manually:

```bash
aws lambda invoke \
  --region ap-southeast-4 \
  --function-name "$(terraform output -raw rds_connectivity_lambda_name)" \
  --cli-binary-format raw-in-base64-out \
  --payload '{}' \
  --log-type Tail \
  /tmp/rds-connectivity-response.json

cat /tmp/rds-connectivity-response.json
```

A successful check returns `{"status":"ok"}` without `FunctionError`.

## Apply database migrations

Terraform deploys an internal migration Lambda but does not invoke it. After
`terraform apply`, run:

```bash
aws lambda invoke \
  --region ap-southeast-4 \
  --function-name "$(terraform output -raw database_migration_lambda_name)" \
  --cli-binary-format raw-in-base64-out \
  --payload '{}' \
  /tmp/database-migration-response.json

cat /tmp/database-migration-response.json
```

Success reports the current migration version. Repeated invocation is safe and
returns `"applied": 0` when the database is current. The migration Lambda has
no API Gateway route and does not load application data.

## Configure location search

Terraform creates the OpenRouteService secret without a value. After deployment,
store the key manually so it never enters Terraform state:

```bash
aws secretsmanager put-secret-value \
  --region ap-southeast-4 \
  --secret-id "$(terraform output -raw ors_api_key_secret_arn)" \
  --secret-string '{"api_key":"YOUR_ORS_API_KEY"}'
```

Then test the endpoint:

```bash
curl --get "$(terraform output -raw location_search_endpoint)" \
  --data-urlencode 'text=State Library Victoria'
```

The location-search Lambda uses public AWS networking and reads only this secret.
It has no RDS access and no VPC attachment.
