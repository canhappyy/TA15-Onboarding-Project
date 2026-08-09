locals {
  refuge_search_function_name = "${local.name_prefix}-refuge-search"
}

resource "aws_iam_role" "refuge_search_execution" {
  name = "${local.name_prefix}-refuge-search-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "refuge_search_basic" {
  role       = aws_iam_role.refuge_search_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "refuge_search_vpc" {
  role       = aws_iam_role.refuge_search_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "refuge_search_secrets" {
  name = "${local.name_prefix}-refuge-search-secrets"
  role = aws_iam_role.refuge_search_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "secretsmanager:GetSecretValue"
      Resource = [
        aws_secretsmanager_secret.ors_api_key.arn,
        aws_secretsmanager_secret.route_database.arn,
      ]
    }]
  })
}

resource "aws_cloudwatch_log_group" "refuge_search" {
  name              = "/aws/lambda/${local.refuge_search_function_name}"
  retention_in_days = 14
}

resource "aws_lambda_function" "refuge_search" {
  function_name = local.refuge_search_function_name

  role         = aws_iam_role.refuge_search_execution.arn
  package_type = "Image"
  image_uri    = local.refuge_search_image_uri

  image_config {
    command = ["src.functions.refuge_search.handler.lambda_handler"]
  }

  architectures = ["arm64"]
  memory_size   = 512
  timeout       = 25

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      DATABASE_HOST          = aws_db_instance.postgres.address
      DATABASE_NAME          = aws_db_instance.postgres.db_name
      DATABASE_PORT          = tostring(aws_db_instance.postgres.port)
      DATABASE_SECRET_ARN    = aws_secretsmanager_secret.route_database.arn
      ORS_API_KEY_SECRET_ARN = aws_secretsmanager_secret.ors_api_key.arn
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.refuge_search,
    aws_iam_role_policy_attachment.refuge_search_basic,
    aws_iam_role_policy_attachment.refuge_search_vpc,
    aws_iam_role_policy.refuge_search_secrets,
    aws_ecr_repository_policy.lambda_pull,
    terraform_data.lambda_images,
  ]
}

resource "aws_apigatewayv2_integration" "refuge_search" {
  api_id = aws_apigatewayv2_api.main.id

  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.refuge_search.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "refuge_search" {
  api_id = aws_apigatewayv2_api.main.id

  route_key          = "GET /refuges"
  target             = "integrations/${aws_apigatewayv2_integration.refuge_search.id}"
  authorization_type = "NONE"
}

resource "aws_apigatewayv2_route" "refuge_search_journey" {
  api_id = aws_apigatewayv2_api.main.id

  route_key          = "POST /refuges/search"
  target             = "integrations/${aws_apigatewayv2_integration.refuge_search.id}"
  authorization_type = "NONE"
}

resource "aws_lambda_permission" "allow_api_gateway_refuge_search" {
  statement_id  = "AllowApiGatewayInvokeRefugeSearch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.refuge_search.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/GET/refuges"
}

resource "aws_lambda_permission" "allow_api_gateway_refuge_search_journey" {
  statement_id  = "AllowApiGatewayInvokeRefugeSearchJourney"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.refuge_search.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/POST/refuges/search"
}
