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
