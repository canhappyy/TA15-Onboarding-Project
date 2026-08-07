resource "aws_iam_role" "lambda_execution" {
  name = "${local.name_prefix}-lambda-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "lambda.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_security_group" "lambda" {
  name        = "${local.name_prefix}-lambda-sg"
  description = "Outbound access for VPC Lambda functions"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-lambda-sg"
  }
}

resource "aws_vpc_security_group_egress_rule" "lambda_ipv4" {
  security_group_id = aws_security_group.lambda.id
  description       = "Allow Lambda outbound traffic"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_security_group" "rds" {
  name        = "${local.name_prefix}-rds-sg"
  description = "PostgreSQL access from VPC Lambda functions only"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-rds-sg"
  }
}

resource "aws_vpc_security_group_ingress_rule" "postgres_from_lambda" {
  security_group_id            = aws_security_group.rds.id
  referenced_security_group_id = aws_security_group.lambda.id
  description                  = "PostgreSQL from Lambda security group"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}
