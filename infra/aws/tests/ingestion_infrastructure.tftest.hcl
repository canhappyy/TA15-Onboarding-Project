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

  mock_resource "aws_ecr_repository" {
    defaults = {
      arn            = "arn:aws:ecr:ap-southeast-4:123456789012:repository/mock"
      repository_url = "123456789012.dkr.ecr.ap-southeast-4.amazonaws.com/mock"
    }
  }

  mock_data "aws_ecr_image" {
    defaults = {
      image_digest = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  }

  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "123456789012"
    }
  }

  mock_data "aws_partition" {
    defaults = {
      partition = "aws"
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
      url = "https://sqs.ap-southeast-4.amazonaws.com/123456789012/mock-dlq"
    }
  }

  mock_resource "aws_sns_topic" {
    defaults = {
      arn = "arn:aws:sns:ap-southeast-4:123456789012:ingestion-alerts"
    }
  }
}

variables {
  build_lambda_images         = false
  ingestion_schedules_enabled = false
}

run "ingestion_infrastructure_plan" {
  command = apply

  override_resource {
    target = aws_ecr_repository.ingestion
    values = {
      repository_url = "123456789012.dkr.ecr.ap-southeast-4.amazonaws.com/ingestion"
    }
  }

  override_resource {
    target = aws_ecr_repository.database_migration
    values = {
      repository_url = "123456789012.dkr.ecr.ap-southeast-4.amazonaws.com/database-migration"
    }
  }

  override_resource {
    target = aws_ecr_repository.rds_connectivity
    values = {
      repository_url = "123456789012.dkr.ecr.ap-southeast-4.amazonaws.com/rds-connectivity"
    }
  }

  assert {
    condition = (
      aws_ecr_repository.ingestion.image_scanning_configuration[0].scan_on_push &&
      aws_ecr_repository.database_migration.image_scanning_configuration[0].scan_on_push &&
      aws_ecr_repository.rds_connectivity.image_scanning_configuration[0].scan_on_push &&
      aws_ecr_repository.ingestion.image_tag_mutability == "IMMUTABLE" &&
      aws_ecr_repository.database_migration.image_tag_mutability == "IMMUTABLE" &&
      aws_ecr_repository.rds_connectivity.image_tag_mutability == "IMMUTABLE"
    )
    error_message = "All three Lambda image repositories must scan immutable images."
  }

  assert {
    condition = alltrue([
      for policy in values(aws_ecr_repository_policy.lambda_pull) :
      contains(jsondecode(policy.policy).Statement[0].Action, "ecr:BatchGetImage") &&
      contains(jsondecode(policy.policy).Statement[0].Action, "ecr:GetDownloadUrlForLayer") &&
      jsondecode(policy.policy).Statement[0].Condition.StringEquals["aws:SourceAccount"] == "123456789012" &&
      jsondecode(policy.policy).Statement[0].Condition.ArnLike["aws:SourceArn"] == "arn:aws:lambda:ap-southeast-4:123456789012:function:ta15-onboarding-dev-*"
    ])
    error_message = "ECR pulls must be limited to project Lambdas in the current account."
  }

  assert {
    condition = (
      aws_lambda_function.ingestion.package_type == "Image" &&
      strcontains(aws_lambda_function.ingestion.image_uri, "@sha256:") &&
      aws_lambda_function.ingestion.architectures == tolist(["arm64"]) &&
      aws_lambda_function.ingestion.image_config[0].command == tolist(["src.functions.ingestion.handler.lambda_handler"]) &&
      aws_lambda_function.ingestion.timeout == 900 &&
      aws_lambda_function.ingestion.memory_size == 1024 &&
      aws_lambda_function.ingestion.reserved_concurrent_executions == null
    )
    error_message = "Ingestion Lambda must use the ARM64 image without reserved concurrency."
  }

  assert {
    condition = (
      length(aws_lambda_function.ingestion.vpc_config[0].subnet_ids) == 2 &&
      length(aws_lambda_function.ingestion.vpc_config[0].security_group_ids) == 1 &&
      toset(keys(aws_lambda_function.ingestion.environment[0].variables)) == toset([
        "DATABASE_HOST",
        "DATABASE_NAME",
        "DATABASE_PORT",
        "DATABASE_SECRET_ARN",
        "ENVIRONMENT",
        "METRIC_NAMESPACE",
      ])
    )
    error_message = "Ingestion Lambda must use private database networking and configuration."
  }

  assert {
    condition = (
      aws_lambda_function.rds_connectivity.package_type == "Image" &&
      aws_lambda_function.database_migration.package_type == "Image" &&
      strcontains(aws_lambda_function.rds_connectivity.image_uri, "@sha256:") &&
      strcontains(aws_lambda_function.database_migration.image_uri, "@sha256:") &&
      aws_lambda_function.rds_connectivity.image_uri != aws_lambda_function.database_migration.image_uri &&
      aws_lambda_function.rds_connectivity.image_config[0].command == tolist(["src.functions.rds_connectivity.handler.lambda_handler"]) &&
      aws_lambda_function.database_migration.image_config[0].command == tolist(["src.functions.database_migration.handler.lambda_handler"])
    )
    error_message = "Connectivity and migration Lambdas must use independent digest images and commands."
  }

  assert {
    condition = alltrue([
      for schedule in values(aws_scheduler_schedule.ingestion) :
      schedule.state == "DISABLED" &&
      schedule.schedule_expression_timezone == "Australia/Melbourne" &&
      schedule.target[0].dead_letter_config[0].arn == aws_sqs_queue.ingestion_dlq.arn &&
      schedule.target[0].retry_policy[0].maximum_retry_attempts == 2
    ])
    error_message = "All ingestion schedules must be timezone-aware, disabled, retried, and connected to the DLQ."
  }

  assert {
    condition = (
      jsondecode(aws_scheduler_schedule.ingestion["minute"].target[0].input).mode == "minute" &&
      jsondecode(aws_scheduler_schedule.ingestion["hourly"].target[0].input).mode == "hourly" &&
      jsondecode(aws_scheduler_schedule.ingestion["static"].target[0].input).mode == "static"
    )
    error_message = "Schedules must invoke their matching ingestion modes."
  }

  assert {
    condition = (
      aws_cloudwatch_log_group.ingestion.retention_in_days == 14 &&
      aws_sqs_queue.ingestion_dlq.message_retention_seconds == 1209600 &&
      aws_cloudwatch_metric_alarm.ingestion_errors.threshold == 1 &&
      aws_cloudwatch_metric_alarm.ingestion_dlq_messages.threshold == 1 &&
      aws_cloudwatch_metric_alarm.ingestion_errors.alarm_actions == toset([aws_sns_topic.ingestion_alerts.arn]) &&
      aws_cloudwatch_metric_alarm.ingestion_dlq_messages.alarm_actions == toset([aws_sns_topic.ingestion_alerts.arn])
    )
    error_message = "Ingestion must retain logs, retain failed events, and route alarms to SNS."
  }

  assert {
    condition = (
      aws_cloudwatch_metric_alarm.ingestion_freshness.namespace == "ClearWay/Ingestion" &&
      aws_cloudwatch_metric_alarm.ingestion_freshness.metric_name == "MinuteDataFresh" &&
      aws_cloudwatch_metric_alarm.ingestion_freshness.statistic == "Minimum" &&
      aws_cloudwatch_metric_alarm.ingestion_freshness.period == 900 &&
      aws_cloudwatch_metric_alarm.ingestion_freshness.evaluation_periods == 3 &&
      aws_cloudwatch_metric_alarm.ingestion_freshness.datapoints_to_alarm == 2 &&
      aws_cloudwatch_metric_alarm.ingestion_freshness.comparison_operator == "LessThanThreshold" &&
      aws_cloudwatch_metric_alarm.ingestion_freshness.threshold == 1 &&
      aws_cloudwatch_metric_alarm.ingestion_freshness.treat_missing_data == "breaching" &&
      aws_cloudwatch_metric_alarm.ingestion_freshness.actions_enabled == false &&
      aws_cloudwatch_metric_alarm.ingestion_freshness.dimensions == tomap({ Environment = "dev" }) &&
      aws_cloudwatch_metric_alarm.ingestion_freshness.alarm_actions == toset([aws_sns_topic.ingestion_alerts.arn])
    )
    error_message = "Minute freshness alarm must detect stale or missing ingestion and notify the existing SNS topic."
  }

  assert {
    condition = (
      aws_lambda_function_event_invoke_config.ingestion.maximum_retry_attempts == 2 &&
      aws_lambda_function_event_invoke_config.ingestion.maximum_event_age_in_seconds == 3600 &&
      aws_lambda_function_event_invoke_config.ingestion.destination_config[0].on_failure[0].destination == aws_sqs_queue.ingestion_dlq.arn
    )
    error_message = "Asynchronous handler failures must retry and reach the ingestion DLQ."
  }

  assert {
    condition = (
      output.ingestion_lambda_name == "ta15-onboarding-dev-ingestion" &&
      output.ingestion_schedules_enabled == false &&
      output.ingestion_freshness_alarm_name == "ta15-onboarding-dev-ingestion-minute-freshness"
    )
    error_message = "Ingestion deployment outputs must expose the function and schedule state."
  }
}
