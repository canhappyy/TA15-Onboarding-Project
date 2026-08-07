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

run "network_database_plan" {
  command = apply

  assert {
    condition     = aws_vpc.main.cidr_block == "10.20.0.0/16"
    error_message = "VPC must use 10.20.0.0/16."
  }

  assert {
    condition = [
      aws_subnet.public[0].cidr_block,
      aws_subnet.public[1].cidr_block,
    ] == ["10.20.0.0/24", "10.20.1.0/24"]
    error_message = "Public subnet CIDRs must match the approved network plan."
  }

  assert {
    condition = [
      aws_subnet.private[0].cidr_block,
      aws_subnet.private[1].cidr_block,
    ] == ["10.20.10.0/24", "10.20.11.0/24"]
    error_message = "Private subnet CIDRs must match the approved network plan."
  }

  assert {
    condition     = aws_subnet.public[0].availability_zone != aws_subnet.public[1].availability_zone
    error_message = "Public subnets must use distinct availability zones."
  }

  assert {
    condition     = aws_subnet.private[0].availability_zone != aws_subnet.private[1].availability_zone
    error_message = "Private subnets must use distinct availability zones."
  }

  assert {
    condition     = aws_route.private_default.nat_gateway_id == aws_nat_gateway.main.id
    error_message = "Private subnet traffic must use the NAT gateway."
  }

  assert {
    condition     = aws_db_instance.postgres.engine == "postgres" && aws_db_instance.postgres.engine_version == "16"
    error_message = "Database must use PostgreSQL 16."
  }

  assert {
    condition     = aws_db_instance.postgres.instance_class == "db.t4g.micro" && aws_db_instance.postgres.multi_az == false
    error_message = "Database must be a Single-AZ db.t4g.micro instance."
  }

  assert {
    condition     = aws_db_instance.postgres.allocated_storage == 20 && aws_db_instance.postgres.storage_type == "gp3"
    error_message = "Database must use 20 GB of gp3 storage."
  }

  assert {
    condition     = aws_db_instance.postgres.storage_encrypted == true && aws_db_instance.postgres.publicly_accessible == false
    error_message = "Database must be encrypted and private."
  }

  assert {
    condition     = aws_db_instance.postgres.backup_retention_period == 1
    error_message = "Database backups must use the one-day AWS Free-plan limit."
  }

  assert {
    condition     = aws_db_instance.postgres.manage_master_user_password == true
    error_message = "Database password must be managed by AWS Secrets Manager."
  }

  assert {
    condition = (
      aws_vpc_security_group_ingress_rule.postgres_from_lambda.from_port == 5432 &&
      aws_vpc_security_group_ingress_rule.postgres_from_lambda.to_port == 5432 &&
      aws_vpc_security_group_ingress_rule.postgres_from_lambda.ip_protocol == "tcp" &&
      aws_vpc_security_group_ingress_rule.postgres_from_lambda.referenced_security_group_id == aws_security_group.lambda.id
    )
    error_message = "PostgreSQL ingress must allow port 5432 only from the Lambda security group."
  }

  assert {
    condition = (
      aws_vpc_security_group_egress_rule.lambda_ipv4.ip_protocol == "-1" &&
      aws_vpc_security_group_egress_rule.lambda_ipv4.cidr_ipv4 == "0.0.0.0/0"
    )
    error_message = "Lambda functions must have outbound IPv4 access through the private subnet NAT route."
  }

  assert {
    condition     = output.database_port == 5432 && output.database_name == "clearway"
    error_message = "Database outputs must expose the approved port and database name."
  }

  assert {
    condition = (
      length(output.public_subnet_ids) == 2 &&
      length(output.private_subnet_ids) == 2 &&
      output.database_secret_arn == "arn:aws:secretsmanager:ap-southeast-4:123456789012:secret:mock"
    )
    error_message = "Network and managed-secret outputs must be exposed without credentials."
  }
}
