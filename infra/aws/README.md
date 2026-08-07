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
