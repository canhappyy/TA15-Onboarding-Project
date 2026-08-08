locals {
  database_migrations_path = "${path.module}/../../packages/database/migrations"
}

data "archive_file" "database_migration_lambda" {
  type        = "zip"
  output_path = "${path.module}/.terraform-build/database-migration-lambda.zip"

  source {
    content  = file("${path.module}/../../services/api/src/functions/database_migration/handler.py")
    filename = "handler.py"
  }

  dynamic "source" {
    for_each = fileset(local.database_migrations_path, "*.sql")
    content {
      content  = file("${local.database_migrations_path}/${source.value}")
      filename = "migrations/${source.value}"
    }
  }
}

resource "aws_lambda_function" "database_migration" {
  function_name = "${local.name_prefix}-database-migration"

  role    = aws_iam_role.database_migration_execution.arn
  handler = "handler.lambda_handler"
  runtime = "python3.13"

  filename         = data.archive_file.database_migration_lambda.output_path
  source_code_hash = data.archive_file.database_migration_lambda.output_base64sha256

  memory_size = 256
  timeout     = 60

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
      MIGRATIONS_PATH     = "/var/task/migrations"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.database_migration_basic,
    aws_iam_role_policy_attachment.database_migration_vpc,
    aws_iam_role_policy.database_migration_secret,
  ]
}
