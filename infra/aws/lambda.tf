data "archive_file" "health_lambda" {
  type = "zip"

  source_dir = "${path.module}/../../services/api/src/functions/health"

  output_path = "${path.module}/.terraform-build/health-lambda.zip"
}

resource "aws_lambda_function" "health" {
  function_name = "${local.name_prefix}-health"

  role    = aws_iam_role.lambda_execution.arn
  handler = "handler.lambda_handler"
  runtime = "python3.13"

  filename         = data.archive_file.health_lambda.output_path
  source_code_hash = data.archive_file.health_lambda.output_base64sha256

  memory_size = 128
  timeout     = 5

  architectures = ["arm64"]

  environment {
    variables = {
      APP_ENV = var.environment
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution
  ]
}