output "api_base_url" {
  description = "Base URL of the HTTP API"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "health_endpoint" {
  description = "Health-check endpoint"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/health"
}

output "health_lambda_name" {
  description = "Name of the deployed health Lambda"
  value       = aws_lambda_function.health.function_name
}