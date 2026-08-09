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

output "database_migration_lambda_name" {
  description = "Name of the internal Lambda used for manual database migrations"
  value       = aws_lambda_function.database_migration.function_name
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

output "ingestion_lambda_name" {
  description = "Name of the internal Open Data ingestion Lambda"
  value       = aws_lambda_function.ingestion.function_name
}

output "ingestion_repository_url" {
  description = "ECR repository used by the ingestion Lambda"
  value       = aws_ecr_repository.ingestion.repository_url
}

output "database_migration_repository_url" {
  description = "ECR repository used by the database migration Lambda"
  value       = aws_ecr_repository.database_migration.repository_url
}

output "rds_connectivity_repository_url" {
  description = "ECR repository used by the RDS connectivity Lambda"
  value       = aws_ecr_repository.rds_connectivity.repository_url
}

output "ingestion_schedules_enabled" {
  description = "Whether recurring ingestion schedules are enabled"
  value       = var.ingestion_schedules_enabled
}

output "ingestion_alert_topic_arn" {
  description = "SNS topic receiving ingestion alarm notifications"
  value       = aws_sns_topic.ingestion_alerts.arn
}

output "route_search_endpoint" {
  description = "Sensory-aware walking route search endpoint"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/routes/search"
}

output "route_search_lambda_name" {
  description = "Name of the route-search Lambda"
  value       = aws_lambda_function.route_search.function_name
}

output "route_database_secret_arn" {
  description = "ARN of the read-only route-search database secret"
  value       = aws_secretsmanager_secret.route_database.arn
}

output "route_search_repository_url" {
  description = "ECR repository used by the route-search Lambda"
  value       = aws_ecr_repository.route_search.repository_url
}

output "refuge_search_endpoint" {
  description = "Nearby quiet-space refuge search endpoint"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/refuges"
}

output "refuge_search_lambda_name" {
  description = "Name of the refuge-search Lambda"
  value       = aws_lambda_function.refuge_search.function_name
}

output "refuge_search_repository_url" {
  description = "ECR repository used by the refuge-search Lambda"
  value       = aws_ecr_repository.refuge_search.repository_url
}
