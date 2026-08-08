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
        secret_arn    = "arn:aws:secretsmanager:ap-southeast-4:123456789012:secret:mock"
        secret_status = "active"
      }]
    }
  }

  mock_resource "aws_apigatewayv2_api" {
    defaults = {
      execution_arn = "arn:aws:execute-api:ap-southeast-4:123456789012:mock-api"
    }
  }

}

variables {
  build_lambda_images = false
}

run "rds_connectivity_plan" {
  command = apply

  assert {
    condition = (
      aws_lambda_function.rds_connectivity.package_type == "Image" &&
      aws_lambda_function.rds_connectivity.image_config[0].command == tolist(["src.functions.rds_connectivity.handler.lambda_handler"]) &&
      aws_lambda_function.rds_connectivity.architectures == tolist(["arm64"])
    )
    error_message = "Connectivity Lambda must use its independent ARM64 image."
  }

  assert {
    condition = (
      length(aws_lambda_function.rds_connectivity.vpc_config[0].subnet_ids) == 2 &&
      length(aws_lambda_function.rds_connectivity.vpc_config[0].security_group_ids) == 1
    )
    error_message = "Connectivity Lambda must use both private subnets and the Lambda security group."
  }

  assert {
    condition = (
      toset(keys(aws_lambda_function.rds_connectivity.environment[0].variables)) == toset([
        "DATABASE_HOST",
        "DATABASE_NAME",
        "DATABASE_PORT",
        "DATABASE_SECRET_ARN",
      ])
    )
    error_message = "Connectivity Lambda must receive complete database configuration."
  }

  assert {
    condition = (
      aws_lambda_function.rds_connectivity.environment[0].variables.DATABASE_HOST == aws_db_instance.postgres.address &&
      aws_lambda_function.rds_connectivity.environment[0].variables.DATABASE_NAME == "clearway" &&
      aws_lambda_function.rds_connectivity.environment[0].variables.DATABASE_PORT == "5432"
    )
    error_message = "Connectivity Lambda must receive host, database name, and port from Terraform."
  }

  assert {
    condition = (
      aws_iam_role_policy_attachment.rds_connectivity_basic.policy_arn == "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" &&
      aws_iam_role_policy_attachment.rds_connectivity_vpc.policy_arn == "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
    )
    error_message = "Connectivity Lambda needs logging and VPC network-interface permissions."
  }

  assert {
    condition     = jsondecode(aws_iam_role_policy.rds_connectivity_secret.policy).Statement[0].Action == "secretsmanager:GetSecretValue"
    error_message = "Connectivity Lambda must read the RDS-managed secret."
  }

  assert {
    condition     = aws_apigatewayv2_route.health.route_key == "GET /health"
    error_message = "Connectivity work must leave API Gateway limited to the existing health route."
  }

  assert {
    condition     = output.rds_connectivity_lambda_name == "ta15-onboarding-dev-rds-connectivity"
    error_message = "Connectivity Lambda name must be available for manual invocation."
  }
}
