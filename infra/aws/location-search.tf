resource "aws_secretsmanager_secret" "ors_api_key" {
  name                    = "${local.name_prefix}/openrouteservice-api-key"
  description             = "OpenRouteService API key used by the location-search Lambda"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0
}

resource "aws_iam_role" "location_search_execution" {
  name = "${local.name_prefix}-location-search-role"

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

resource "aws_iam_role_policy_attachment" "location_search_basic" {
  role       = aws_iam_role.location_search_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "location_search_secret" {
  name = "${local.name_prefix}-location-search-secret"
  role = aws_iam_role.location_search_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = aws_secretsmanager_secret.ors_api_key.arn
    }]
  })
}

data "archive_file" "location_search_lambda" {
  type        = "zip"
  output_path = "${path.module}/.terraform-build/location-search-lambda.zip"

  source {
    content  = file("${path.module}/../../services/api/src/clients/__init__.py")
    filename = "src/clients/__init__.py"
  }

  source {
    content  = file("${path.module}/../../services/api/src/clients/open_route_service.py")
    filename = "src/clients/open_route_service.py"
  }

  source {
    content  = file("${path.module}/../../services/api/src/common/__init__.py")
    filename = "src/common/__init__.py"
  }

  source {
    content  = file("${path.module}/../../services/api/src/common/geojson.py")
    filename = "src/common/geojson.py"
  }

  source {
    content  = file("${path.module}/../../services/api/src/common/responses.py")
    filename = "src/common/responses.py"
  }

  source {
    content  = file("${path.module}/../../services/api/src/functions/location_search/__init__.py")
    filename = "src/functions/location_search/__init__.py"
  }

  source {
    content  = file("${path.module}/../../services/api/src/functions/location_search/handler.py")
    filename = "src/functions/location_search/handler.py"
  }

  source {
    content  = file("${path.module}/../../services/api/src/functions/location_search/assets/city-of-melbourne-boundary-2022.geojson")
    filename = "src/functions/location_search/assets/city-of-melbourne-boundary-2022.geojson"
  }
}

resource "aws_lambda_function" "location_search" {
  function_name = "${local.name_prefix}-location-search"

  role    = aws_iam_role.location_search_execution.arn
  handler = "src.functions.location_search.handler.lambda_handler"
  runtime = "python3.13"

  filename         = data.archive_file.location_search_lambda.output_path
  source_code_hash = data.archive_file.location_search_lambda.output_base64sha256

  architectures = ["arm64"]
  memory_size   = 128
  timeout       = 10

  environment {
    variables = {
      ORS_API_KEY_SECRET_ARN = aws_secretsmanager_secret.ors_api_key.arn
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.location_search_basic,
    aws_iam_role_policy.location_search_secret,
  ]
}

resource "aws_apigatewayv2_integration" "location_search" {
  api_id = aws_apigatewayv2_api.main.id

  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.location_search.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "location_search" {
  api_id = aws_apigatewayv2_api.main.id

  route_key = "GET /locations/search"
  target    = "integrations/${aws_apigatewayv2_integration.location_search.id}"

  authorization_type = "NONE"
}

resource "aws_lambda_permission" "allow_api_gateway_location_search" {
  statement_id  = "AllowApiGatewayInvokeLocationSearch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.location_search.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_apigatewayv2_api.main.execution_arn}/*/GET/locations/search"
}
