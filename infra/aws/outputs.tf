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

output "database_endpoint" {
  description = "Private RDS PostgreSQL hostname"
  value       = aws_db_instance.postgres.address
}

output "database_port" {
  description = "RDS PostgreSQL port"
  value       = aws_db_instance.postgres.port
}

output "database_name" {
  description = "Application database name"
  value       = aws_db_instance.postgres.db_name
}

output "database_secret_arn" {
  description = "ARN of the RDS-managed master-user secret"
  value       = aws_db_instance.postgres.master_user_secret[0].secret_arn
}

output "lambda_security_group_id" {
  description = "Security group ID for VPC Lambda functions"
  value       = aws_security_group.lambda.id
}

output "rds_security_group_id" {
  description = "Security group ID for the private PostgreSQL instance"
  value       = aws_security_group.rds.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

output "rds_connectivity_lambda_name" {
  description = "Name of the internal Lambda used for manual RDS connectivity checks"
  value       = aws_lambda_function.rds_connectivity.function_name
}

output "location_search_endpoint" {
  description = "Location-search endpoint"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/locations/search"
}

output "location_search_lambda_name" {
  description = "Name of the location-search Lambda"
  value       = aws_lambda_function.location_search.function_name
}

output "ors_api_key_secret_arn" {
  description = "ARN of the empty Secrets Manager secret for the OpenRouteService API key"
  value       = aws_secretsmanager_secret.ors_api_key.arn
}
