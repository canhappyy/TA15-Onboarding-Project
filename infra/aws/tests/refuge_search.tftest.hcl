mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = { names = ["ap-southeast-4a", "ap-southeast-4b"] }
  }
  mock_data "aws_ecr_image" {
    defaults = { image_digest = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
  }
  mock_resource "aws_sns_topic" {
    defaults = { arn = "arn:aws:sns:ap-southeast-4:123456789012:alerts" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/mock" }
  }
  mock_resource "aws_lambda_function" {
    defaults = { arn = "arn:aws:lambda:ap-southeast-4:123456789012:function:mock" }
  }
  mock_resource "aws_sqs_queue" {
    defaults = { arn = "arn:aws:sqs:ap-southeast-4:123456789012:mock" }
  }
  mock_resource "aws_db_instance" {
    defaults = {
      master_user_secret = [{
        kms_key_id    = "arn:aws:kms:ap-southeast-4:123456789012:key/mock"
        secret_arn    = "arn:aws:secretsmanager:ap-southeast-4:123456789012:secret:master"
        secret_status = "active"
      }]
    }
  }
  mock_resource "aws_apigatewayv2_api" {
    defaults = { execution_arn = "arn:aws:execute-api:ap-southeast-4:123456789012:api" }
  }
  mock_resource "aws_secretsmanager_secret" {
    defaults = { arn = "arn:aws:secretsmanager:ap-southeast-4:123456789012:secret:mock" }
  }
}

variables {
  build_lambda_images = false
}

run "refuge_search_plan" {
  command = apply

  assert {
    condition = (
      aws_ecr_repository.refuge_search.image_tag_mutability == "IMMUTABLE" &&
      aws_ecr_repository.refuge_search.image_scanning_configuration[0].scan_on_push
    )
    error_message = "Refuge search must use immutable, scanned ECR images."
  }

  assert {
    condition = (
      aws_lambda_function.refuge_search.package_type == "Image" &&
      aws_lambda_function.refuge_search.image_uri == "${aws_ecr_repository.refuge_search.repository_url}@${data.aws_ecr_image.refuge_search.image_digest}" &&
      aws_lambda_function.refuge_search.architectures == tolist(["arm64"]) &&
      aws_lambda_function.refuge_search.memory_size == 512 &&
      aws_lambda_function.refuge_search.timeout == 25
    )
    error_message = "Refuge search must use ARM64 container runtime settings."
  }

  assert {
    condition     = aws_lambda_function.refuge_search.image_config[0].command == tolist(["src.functions.refuge_search.handler.lambda_handler"])
    error_message = "Refuge search image must invoke the refuge handler."
  }

  assert {
    condition = (
      aws_lambda_function.refuge_search.vpc_config[0].subnet_ids == toset(aws_subnet.private[*].id) &&
      aws_lambda_function.refuge_search.vpc_config[0].security_group_ids == toset([aws_security_group.lambda.id])
    )
    error_message = "Refuge search must use private subnets and the Lambda security group."
  }

  assert {
    condition = toset(keys(aws_lambda_function.refuge_search.environment[0].variables)) == toset([
      "DATABASE_HOST",
      "DATABASE_NAME",
      "DATABASE_PORT",
      "DATABASE_SECRET_ARN",
      "ORS_API_KEY_SECRET_ARN",
    ])
    error_message = "Refuge search must receive complete database and ORS configuration."
  }

  assert {
    condition = (
      aws_lambda_function.refuge_search.environment[0].variables.DATABASE_SECRET_ARN == aws_secretsmanager_secret.route_database.arn &&
      aws_lambda_function.refuge_search.environment[0].variables.DATABASE_SECRET_ARN != aws_db_instance.postgres.master_user_secret[0].secret_arn &&
      aws_lambda_function.refuge_search.environment[0].variables.DATABASE_HOST == aws_db_instance.postgres.address &&
      aws_lambda_function.refuge_search.environment[0].variables.DATABASE_NAME == aws_db_instance.postgres.db_name &&
      aws_lambda_function.refuge_search.environment[0].variables.DATABASE_PORT == tostring(aws_db_instance.postgres.port) &&
      aws_lambda_function.refuge_search.environment[0].variables.ORS_API_KEY_SECRET_ARN == aws_secretsmanager_secret.ors_api_key.arn
    )
    error_message = "Refuge search must use the dedicated reader secret, never the master secret."
  }

  assert {
    condition = toset(jsondecode(aws_iam_role_policy.refuge_search_secrets.policy).Statement[0].Resource) == toset([
      aws_secretsmanager_secret.ors_api_key.arn,
      aws_secretsmanager_secret.route_database.arn
    ])
    error_message = "Refuge search secret permission must be limited to ORS and reader secrets."
  }

  assert {
    condition = (
      aws_apigatewayv2_route.refuge_search.route_key == "GET /refuges" &&
      aws_apigatewayv2_route.refuge_search.target == "integrations/${aws_apigatewayv2_integration.refuge_search.id}" &&
      aws_apigatewayv2_route.refuge_search.authorization_type == "NONE"
    )
    error_message = "API Gateway must expose GET /refuges."
  }

  assert {
    condition = (
      aws_lambda_permission.allow_api_gateway_refuge_search.action == "lambda:InvokeFunction" &&
      aws_lambda_permission.allow_api_gateway_refuge_search.function_name == aws_lambda_function.refuge_search.function_name &&
      aws_lambda_permission.allow_api_gateway_refuge_search.principal == "apigateway.amazonaws.com" &&
      aws_lambda_permission.allow_api_gateway_refuge_search.source_arn == "${aws_apigatewayv2_api.main.execution_arn}/*/GET/refuges"
    )
    error_message = "Invoke permission must be limited to GET /refuges."
  }

  assert {
    condition     = output.refuge_search_endpoint == "${aws_apigatewayv2_api.main.api_endpoint}/refuges"
    error_message = "Refuge search endpoint must be exported."
  }

  assert {
    condition = (
      aws_apigatewayv2_route.refuge_search_journey.route_key == "POST /refuges/search" &&
      aws_apigatewayv2_route.refuge_search_journey.authorization_type == "NONE"
    )
    error_message = "API Gateway must expose POST /refuges/search."
  }

  assert {
    condition     = aws_apigatewayv2_route.refuge_search_journey.target == "integrations/${aws_apigatewayv2_integration.refuge_search.id}"
    error_message = "Journey refuge search must reuse the refuge Lambda integration."
  }

  assert {
    condition = (
      aws_apigatewayv2_integration.refuge_search.integration_type == "AWS_PROXY" &&
      aws_apigatewayv2_integration.refuge_search.integration_uri == aws_lambda_function.refuge_search.invoke_arn &&
      aws_apigatewayv2_integration.refuge_search.payload_format_version == "2.0"
    )
    error_message = "Both refuge routes must use the Lambda proxy integration."
  }

  assert {
    condition = (
      aws_lambda_permission.allow_api_gateway_refuge_search_journey.action == "lambda:InvokeFunction" &&
      aws_lambda_permission.allow_api_gateway_refuge_search_journey.function_name == aws_lambda_function.refuge_search.function_name &&
      aws_lambda_permission.allow_api_gateway_refuge_search_journey.principal == "apigateway.amazonaws.com" &&
      aws_lambda_permission.allow_api_gateway_refuge_search_journey.source_arn == "${aws_apigatewayv2_api.main.execution_arn}/*/POST/refuges/search"
    )
    error_message = "Invoke permission must be limited to POST /refuges/search."
  }

  assert {
    condition     = output.refuge_search_journey_endpoint == "${aws_apigatewayv2_api.main.api_endpoint}/refuges/search"
    error_message = "Journey refuge endpoint must be exported."
  }
}
