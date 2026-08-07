mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = {
      names = ["ap-southeast-4a", "ap-southeast-4b"]
    }
  }

  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::123456789012:role/mock-lambda-role"
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

  mock_resource "aws_lambda_layer_version" {
    defaults = {
      arn = "arn:aws:lambda:ap-southeast-4:123456789012:layer:mock-psycopg:1"
    }
  }
}

run "rds_connectivity_plan" {
  command = apply

  assert {
    condition = (
      aws_lambda_function.rds_connectivity.handler == "handler.lambda_handler" &&
      aws_lambda_function.rds_connectivity.runtime == "python3.13" &&
      aws_lambda_function.rds_connectivity.architectures == tolist(["arm64"])
    )
    error_message = "Connectivity Lambda must use the Python 3.13 ARM64 handler."
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
      length(aws_lambda_function.rds_connectivity.layers) == 1 &&
      toset(keys(aws_lambda_function.rds_connectivity.environment[0].variables)) == toset([
        "DATABASE_HOST",
        "DATABASE_NAME",
        "DATABASE_PORT",
        "DATABASE_SECRET_ARN",
      ])
    )
    error_message = "Connectivity Lambda must use the psycopg layer and complete database configuration."
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
      aws_lambda_layer_version.psycopg.compatible_architectures == toset(["arm64"]) &&
      aws_lambda_layer_version.psycopg.compatible_runtimes == toset(["python3.13"])
    )
    error_message = "psycopg layer must target Python 3.13 on ARM64."
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
