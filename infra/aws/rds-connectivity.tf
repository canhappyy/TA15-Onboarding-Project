locals {
  psycopg_layer_requirements = "${path.module}/layers/psycopg/requirements.txt"
  psycopg_layer_build_script = "${path.module}/scripts/build_psycopg_layer.sh"
  psycopg_layer_zip          = "${path.module}/.terraform-build/psycopg-layer.zip"
  psycopg_layer_source_hash = sha256(join(":", [
    filesha256(local.psycopg_layer_requirements),
    filesha256(local.psycopg_layer_build_script),
  ]))
}

resource "aws_lambda_layer_version" "psycopg" {
  layer_name          = "${local.name_prefix}-psycopg"
  description         = "psycopg binary dependencies for Python 3.13 ARM64 Lambdas"
  filename            = local.psycopg_layer_zip
  source_code_hash    = base64sha256(local.psycopg_layer_source_hash)
  compatible_runtimes = ["python3.13"]

  compatible_architectures = ["arm64"]
}

data "archive_file" "rds_connectivity_lambda" {
  type = "zip"

  source_dir  = "${path.module}/../../services/api/src/functions/rds_connectivity"
  output_path = "${path.module}/.terraform-build/rds-connectivity-lambda.zip"
}

resource "aws_lambda_function" "rds_connectivity" {
  function_name = "${local.name_prefix}-rds-connectivity"

  role    = aws_iam_role.rds_connectivity_execution.arn
  handler = "handler.lambda_handler"
  runtime = "python3.13"

  filename         = data.archive_file.rds_connectivity_lambda.output_path
  source_code_hash = data.archive_file.rds_connectivity_lambda.output_base64sha256

  memory_size = 256
  timeout     = 15

  architectures = ["arm64"]
  layers        = [aws_lambda_layer_version.psycopg.arn]

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      DATABASE_HOST       = aws_db_instance.postgres.address
      DATABASE_NAME       = aws_db_instance.postgres.db_name
      DATABASE_PORT       = tostring(aws_db_instance.postgres.port)
      DATABASE_SECRET_ARN = aws_db_instance.postgres.master_user_secret[0].secret_arn
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.rds_connectivity_basic,
    aws_iam_role_policy_attachment.rds_connectivity_vpc,
    aws_iam_role_policy.rds_connectivity_secret,
  ]
}
