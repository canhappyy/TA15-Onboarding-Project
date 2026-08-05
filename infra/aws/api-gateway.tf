resource "aws_apigatewayv2_api" "main" {
  name          = "${local.name_prefix}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = var.frontend_origins

    allow_methods = [
      "GET",
      "POST",
      "OPTIONS"
    ]

    allow_headers = [
      "Content-Type"
    ]

    max_age = 300
  }
}

resource "aws_apigatewayv2_integration" "health" {
  api_id = aws_apigatewayv2_api.main.id

  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.health.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "health" {
  api_id = aws_apigatewayv2_api.main.id

  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.health.id}"

  authorization_type = "NONE"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id = aws_apigatewayv2_api.main.id

  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_rate_limit  = 10
    throttling_burst_limit = 20
  }
}

resource "aws_lambda_permission" "allow_api_gateway_health" {
  statement_id  = "AllowApiGatewayInvokeHealth"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.health.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}