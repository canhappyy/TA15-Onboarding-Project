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

run "database_migration_plan" {
  command = apply

  assert {
    condition = (
      aws_lambda_function.database_migration.handler == "handler.lambda_handler" &&
      aws_lambda_function.database_migration.runtime == "python3.13" &&
      aws_lambda_function.database_migration.architectures == tolist(["arm64"])
    )
    error_message = "Migration Lambda must use Python 3.13 on ARM64."
  }

  assert {
    condition = (
      length(aws_lambda_function.database_migration.vpc_config[0].subnet_ids) == 2 &&
      aws_lambda_function.database_migration.vpc_config[0].security_group_ids == toset([aws_security_group.lambda.id])
    )
    error_message = "Migration Lambda must use private subnets and the Lambda security group."
  }

  assert {
    condition = (
      toset(aws_lambda_function.database_migration.layers) == toset([aws_lambda_layer_version.psycopg.arn]) &&
      toset(keys(aws_lambda_function.database_migration.environment[0].variables)) == toset([
        "DATABASE_HOST",
        "DATABASE_NAME",
        "DATABASE_PORT",
        "DATABASE_SECRET_ARN",
        "MIGRATIONS_PATH",
      ])
    )
    error_message = "Migration Lambda must use the database layer and configuration."
  }

  assert {
    condition     = jsondecode(aws_iam_role_policy.database_migration_secret.policy).Statement[0].Resource == aws_db_instance.postgres.master_user_secret[0].secret_arn
    error_message = "Migration Lambda secret access must be limited to the managed RDS secret."
  }

  assert {
    condition     = output.database_migration_lambda_name == "ta15-onboarding-dev-database-migration"
    error_message = "Migration Lambda name must be available for manual invocation."
  }

  assert {
    condition     = aws_apigatewayv2_route.health.route_key == "GET /health"
    error_message = "Migration Lambda must not add an API Gateway route."
  }
}
