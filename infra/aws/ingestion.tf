locals {
  ingestion_function_name = "${local.name_prefix}-ingestion"
  ingestion_schedules = {
    minute = {
      expression  = "rate(15 minutes)"
      description = "Synchronize observed pedestrian minute counts"
    }
    hourly = {
      expression  = "cron(15 2 * * ? *)"
      description = "Synchronize the previous pedestrian hourly day"
    }
    static = {
      expression  = "cron(30 3 ? * SUN *)"
      description = "Synchronize sensors and landmark metadata"
    }
  }
}

resource "aws_cloudwatch_log_group" "ingestion" {
  name              = "/aws/lambda/${local.ingestion_function_name}"
  retention_in_days = 14
}

resource "aws_sqs_queue" "ingestion_dlq" {
  name                      = "${local.name_prefix}-ingestion-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_lambda_function" "ingestion" {
  function_name = local.ingestion_function_name

  role         = aws_iam_role.ingestion_execution.arn
  package_type = "Image"
  image_uri    = local.ingestion_image_uri

  image_config {
    command = ["src.functions.ingestion.handler.lambda_handler"]
  }

  architectures = ["arm64"]
  memory_size   = 1024
  timeout       = 900

  ephemeral_storage {
    size = 1024
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      DATABASE_HOST       = aws_db_instance.postgres.address
      DATABASE_NAME       = aws_db_instance.postgres.db_name
      DATABASE_PORT       = tostring(aws_db_instance.postgres.port)
      DATABASE_SECRET_ARN = aws_db_instance.postgres.master_user_secret[0].secret_arn
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.ingestion,
    aws_iam_role_policy_attachment.ingestion_basic,
    aws_iam_role_policy_attachment.ingestion_vpc,
    aws_iam_role_policy.ingestion_secret,
    aws_iam_role_policy.ingestion_failure_destination,
    aws_ecr_repository_policy.lambda_pull,
    terraform_data.lambda_images,
  ]
}

resource "aws_lambda_function_event_invoke_config" "ingestion" {
  function_name                = aws_lambda_function.ingestion.function_name
  maximum_event_age_in_seconds = 3600
  maximum_retry_attempts       = 2

  destination_config {
    on_failure {
      destination = aws_sqs_queue.ingestion_dlq.arn
    }
  }
}

resource "aws_scheduler_schedule_group" "ingestion" {
  name = "${local.name_prefix}-ingestion"
}

resource "aws_scheduler_schedule" "ingestion" {
  for_each = local.ingestion_schedules

  name                         = "${local.name_prefix}-ingestion-${each.key}"
  group_name                   = aws_scheduler_schedule_group.ingestion.name
  description                  = each.value.description
  schedule_expression          = each.value.expression
  schedule_expression_timezone = "Australia/Melbourne"
  state                        = var.ingestion_schedules_enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.ingestion.arn
    role_arn = aws_iam_role.ingestion_scheduler.arn
    input    = jsonencode({ mode = each.key })

    dead_letter_config {
      arn = aws_sqs_queue.ingestion_dlq.arn
    }

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 2
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "ingestion_errors" {
  alarm_name          = "${local.name_prefix}-ingestion-errors"
  alarm_description   = "Ingestion Lambda reported an error"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ingestion_alerts.arn]

  dimensions = {
    FunctionName = aws_lambda_function.ingestion.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "ingestion_dlq_messages" {
  alarm_name          = "${local.name_prefix}-ingestion-dlq-messages"
  alarm_description   = "Ingestion events reached the dead-letter queue"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ingestion_alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.ingestion_dlq.name
  }
}

resource "aws_sns_topic" "ingestion_alerts" {
  name = "${local.name_prefix}-ingestion-alerts"
}
