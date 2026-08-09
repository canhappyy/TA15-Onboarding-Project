# AWS infrastructure

Terraform deploys ClearWay AWS resources. RDS connectivity, database migration,
ingestion, route search, and refuge search use Python 3.13 ARM64 container
images. Health and location search remain ZIP Lambdas.

## Prerequisites

- Docker Desktop with Buildx running
- AWS CLI authenticated for `ap-southeast-4`
- Terraform 1.15.5 or compatible

## Validate and deploy

From `infra/aws`:

```bash
terraform fmt -check -recursive
terraform init
terraform validate
terraform test
terraform plan
terraform apply
```

The first `terraform apply` creates five private ECR repositories, then builds
and pushes content-addressed ARM64 images before creating the Lambdas. Existing
immutable image tags are reused, so an interrupted apply can be retried. Source
or dependency changes produce new tags automatically.

Docker must run during an apply that needs a new image. No separate psycopg
layer build is required. Set `build_lambda_images = false` only for mocked tests;
a real deployment needs the images.

`terraform destroy` removes ECR and Lambda resources. A later fresh apply builds
and pushes the images again because the ECR repositories are new.

## Optional local image verification

```bash
bash scripts/manage_lambda_images.sh build ingestion clearway-ingestion:dev
bash scripts/manage_lambda_images.sh verify ingestion clearway-ingestion:dev

bash scripts/manage_lambda_images.sh build database_migration clearway-database-migration:dev
bash scripts/manage_lambda_images.sh verify database_migration clearway-database-migration:dev

bash scripts/manage_lambda_images.sh build rds_connectivity clearway-rds-connectivity:dev
bash scripts/manage_lambda_images.sh verify rds_connectivity clearway-rds-connectivity:dev

bash scripts/manage_lambda_images.sh build route_search clearway-route-search:dev
bash scripts/manage_lambda_images.sh verify route_search clearway-route-search:dev

bash scripts/manage_lambda_images.sh build refuge_search clearway-refuge-search:dev
bash scripts/manage_lambda_images.sh verify refuge_search clearway-refuge-search:dev
```

Each containerized function owns the Dockerfile beside its handler. The one
management script provides local build/verification and Terraform ECR publish
behavior.

Runtime dependencies are hash-locked in
`services/api/requirements-ingestion.txt` and
`services/api/requirements-database-tools.txt`.

## Post-deployment checks

Check private RDS connectivity:

```bash
aws lambda invoke \
  --region ap-southeast-4 \
  --function-name "$(terraform output -raw rds_connectivity_lambda_name)" \
  --cli-binary-format raw-in-base64-out \
  --payload '{}' \
  /tmp/rds-connectivity-response.json

cat /tmp/rds-connectivity-response.json
```

Apply idempotent database migrations. This also creates the restricted route
reader and populates its initially empty Secrets Manager secret:

```bash
aws lambda invoke \
  --region ap-southeast-4 \
  --function-name "$(terraform output -raw database_migration_lambda_name)" \
  --cli-binary-format raw-in-base64-out \
  --payload '{}' \
  /tmp/database-migration-response.json

cat /tmp/database-migration-response.json
```

Verify the route reader secret now has a current version:

```bash
aws secretsmanager describe-secret \
  --region ap-southeast-4 \
  --secret-id "$(terraform output -raw route_database_secret_arn)" \
  --query 'VersionIdsToStages'
```

Run bootstrap ingestion after migration:

```bash
aws lambda invoke \
  --region ap-southeast-4 \
  --function-name "$(terraform output -raw ingestion_lambda_name)" \
  --cli-binary-format raw-in-base64-out \
  --payload '{"mode":"bootstrap"}' \
  /tmp/ingestion-bootstrap-response.json

cat /tmp/ingestion-bootstrap-response.json
```

Successful `bootstrap` and `minute` responses include operational pedestrian
freshness:

```json
{
  "freshness": {
    "minute": {
      "observedAt": "2026-08-09T10:15:00+10:00",
      "ageSeconds": 900,
      "stale": false,
      "thresholdSeconds": 2700
    }
  }
}
```

The timestamp is the latest real, non-imputed observation. Missing observations
use `null` for `observedAt` and `ageSeconds` and set `stale` to `true`. Exactly
45 minutes remains operationally fresh; older data is stale. The route API keeps
its stricter 30-minute user-facing warning so commuters learn about possible
fallback use before the operational alert fires.

Invoke read-only status and require a non-null observation, `ageSeconds <= 2700`,
and `stale == false` before enabling schedules:

```bash
aws lambda invoke \
  --region ap-southeast-4 \
  --function-name "$(terraform output -raw ingestion_lambda_name)" \
  --cli-binary-format raw-in-base64-out \
  --payload '{"mode":"status"}' \
  /tmp/ingestion-status-response.json

jq '.freshness.minute' /tmp/ingestion-status-response.json
```

Successful `bootstrap` and `minute` runs emit `MinuteDataFresh` and, when an
observation exists, `MinuteDataAgeSeconds` in the `ClearWay/Ingestion` namespace.
Status checks, skipped concurrent runs, and failures emit no freshness metric,
so manual checks cannot hide a missed schedule. The freshness alarm evaluates
three 15-minute periods and alarms when two are stale or missing.

Minute, hourly, and static schedules start disabled. Enable them only after the
migration, bootstrap, checkpoint, and row-count smoke tests pass:

```bash
terraform apply -var='ingestion_schedules_enabled=true'
```

The ingestion alarms publish to `ingestion_alert_topic_arn`. Terraform creates
no recipient automatically. Before enabling notifications, require at least one
confirmed operations subscription; `PendingConfirmation` is not sufficient:

```bash
aws sns list-subscriptions-by-topic \
  --region ap-southeast-4 \
  --topic-arn "$(terraform output -raw ingestion_alert_topic_arn)" \
  --query 'Subscriptions[?SubscriptionArn!=`PendingConfirmation`]'
```

Freshness alarm actions stay disabled while `ingestion_schedules_enabled=false`.
After enabling schedules, wait for two fresh datapoints and require `OK`:

```bash
aws cloudwatch describe-alarms \
  --region ap-southeast-4 \
  --alarm-names "$(terraform output -raw ingestion_freshness_alarm_name)" \
  --query 'MetricAlarms[0].StateValue' \
  --output text
```

## Configure location search

Terraform creates the OpenRouteService secret without a value. Store the key
after deployment so it never enters Terraform state:

```bash
aws secretsmanager put-secret-value \
  --region ap-southeast-4 \
  --secret-id "$(terraform output -raw ors_api_key_secret_arn)" \
  --secret-string '{"api_key":"YOUR_ORS_API_KEY"}'
```

## Test route search

After migrations, bootstrap ingestion, and ORS secret configuration:

```bash
curl --fail-with-body \
  --request POST \
  --header 'Content-Type: application/json' \
  --data '{"origin":{"latitude":-37.8179,"longitude":144.9671},"destination":{"latitude":-37.8098,"longitude":144.9652}}' \
  "$(terraform output -raw route_search_endpoint)"
```

## Test refuge search

After migrations, bootstrap ingestion, and ORS secret configuration:

```bash
curl --fail-with-body \
  "$(terraform output -raw refuge_search_endpoint)?latitude=-37.8136&longitude=144.9631"
```
