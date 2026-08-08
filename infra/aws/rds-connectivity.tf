resource "aws_lambda_function" "rds_connectivity" {
  function_name = "${local.name_prefix}-rds-connectivity"

  role         = aws_iam_role.rds_connectivity_execution.arn
  package_type = "Image"
  image_uri    = local.rds_connectivity_image_uri

  image_config {
    command = ["src.functions.rds_connectivity.handler.lambda_handler"]
  }

  memory_size = 256
  timeout     = 15

  architectures = ["arm64"]

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
    aws_ecr_repository_policy.lambda_pull,
    terraform_data.lambda_images,
  ]
}
