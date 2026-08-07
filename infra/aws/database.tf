resource "aws_db_subnet_group" "postgres" {
  name       = "${local.name_prefix}-postgres-subnets"
  subnet_ids = aws_subnet.private[*].id

  tags = {
    Name = "${local.name_prefix}-postgres-subnets"
  }
}

resource "aws_db_instance" "postgres" {
  identifier = "${local.name_prefix}-postgres"

  engine         = "postgres"
  engine_version = "16"
  instance_class = "db.t4g.micro"

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "clearway"
  username = "clearway_admin"
  port     = 5432

  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period    = 7
  auto_minor_version_upgrade = true
  copy_tags_to_snapshot      = true

  deletion_protection = false
  skip_final_snapshot = true

  tags = {
    Name = "${local.name_prefix}-postgres"
  }
}
