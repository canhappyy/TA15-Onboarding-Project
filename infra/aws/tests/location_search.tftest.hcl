mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = {
      names = ["ap-southeast-4a", "ap-southeast-4b"]
    }
  }

  mock_data "aws_ecr_image" {
    defaults = {
      image_digest = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  }

  mock_resource "aws_sns_topic" {
    defaults = {
      arn = "arn:aws:sns:ap-southeast-4:123456789012:ingestion-alerts"
    }
  }

  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::123456789012:role/mock-lambda-role"
    }
  }

  mock_resource "aws_lambda_function" {
    defaults = {
      arn = "arn:aws:lambda:ap-southeast-4:123456789012:function:mock"
    }
  }

  mock_resource "aws_sqs_queue" {
    defaults = {
      arn = "arn:aws:sqs:ap-southeast-4:123456789012:mock-dlq"
    }
  }

  mock_resource "aws_db_instance" {
    defaults = {
      master_user_secret = [{
        kms_key_id    = "arn:aws:kms:ap-southeast-4:123456789012:key/mock"
        secret_arn    = "arn:aws:secretsmanager:ap-southeast-4:123456789012:secret:rds-mock"
        secret_status = "active"
      }]
    }
  }

  mock_resource "aws_apigatewayv2_api" {
    defaults = {
      execution_arn = "arn:aws:execute-api:ap-southeast-4:123456789012:mock-api"
    }
  }


  mock_resource "aws_secretsmanager_secret" {
    defaults = {
      arn = "arn:aws:secretsmanager:ap-southeast-4:123456789012:secret:ors-mock"
    }
  }
}

variables {
  build_lambda_images = false
}

run "location_search_plan" {
  command = apply

  assert {
    condition = (
      aws_lambda_function.location_search.handler == "src.functions.location_search.handler.lambda_handler" &&
      aws_lambda_function.location_search.runtime == "python3.13" &&
      aws_lambda_function.location_search.architectures == tolist(["arm64"])
    )
    error_message = "Location search Lambda must use the Python 3.13 ARM64 handler."
  }

  assert {
    condition = (
      length(aws_lambda_function.location_search.vpc_config) == 0 &&
      aws_lambda_function.location_search.layers == null
    )
    error_message = "Location search Lambda must use public AWS networking without database layers."
  }

  assert {
    condition = (
      toset(keys(aws_lambda_function.location_search.environment[0].variables)) == toset(["ORS_API_KEY_SECRET_ARN"]) &&
      aws_lambda_function.location_search.environment[0].variables.ORS_API_KEY_SECRET_ARN == aws_secretsmanager_secret.ors_api_key.arn
    )
    error_message = "Location search Lambda must receive only the ORS secret ARN."
  }

  assert {
    condition = (
      jsondecode(aws_iam_role_policy.location_search_secret.policy).Statement[0].Action == "secretsmanager:GetSecretValue" &&
      jsondecode(aws_iam_role_policy.location_search_secret.policy).Statement[0].Resource == aws_secretsmanager_secret.ors_api_key.arn
    )
    error_message = "Location search Lambda must have least-privilege access to the ORS secret."
  }

  assert {
    condition     = aws_apigatewayv2_route.location_search.route_key == "GET /locations/search"
    error_message = "API Gateway must expose GET /locations/search."
  }

  assert {
    condition     = aws_lambda_permission.allow_api_gateway_location_search.source_arn == "${aws_apigatewayv2_api.main.execution_arn}/*/GET/locations/search"
    error_message = "API Gateway invoke permission must be limited to GET /locations/search."
  }

  assert {
    condition     = output.ors_api_key_secret_arn == aws_secretsmanager_secret.ors_api_key.arn
    error_message = "The empty ORS secret ARN must be available for manual population."
  }

  assert {
    condition     = output.location_search_endpoint == "${aws_apigatewayv2_api.main.api_endpoint}/locations/search"
    error_message = "The location search endpoint must be exposed as an output."
  }
}
