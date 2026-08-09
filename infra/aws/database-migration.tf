resource "aws_lambda_function" "database_migration" {
  function_name = "${local.name_prefix}-database-migration"

  role         = aws_iam_role.database_migration_execution.arn
  package_type = "Image"
  image_uri    = local.database_migration_image_uri

  image_config {
    command = ["src.functions.database_migration.handler.lambda_handler"]
  }

  memory_size = 256
  timeout     = 60

  architectures = ["arm64"]

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      DATABASE_HOST             = aws_db_instance.postgres.address
      DATABASE_NAME             = aws_db_instance.postgres.db_name
      DATABASE_PORT             = tostring(aws_db_instance.postgres.port)
      DATABASE_SECRET_ARN       = aws_db_instance.postgres.master_user_secret[0].secret_arn
      ROUTE_DATABASE_SECRET_ARN = aws_secretsmanager_secret.route_database.arn
      MIGRATIONS_PATH           = "/var/task/migrations"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.database_migration_basic,
    aws_iam_role_policy_attachment.database_migration_vpc,
    aws_iam_role_policy.database_migration_secret,
    aws_iam_role_policy.database_migration_route_secret,
    aws_ecr_repository_policy.lambda_pull,
    terraform_data.lambda_images,
  ]
}
