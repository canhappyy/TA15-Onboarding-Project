locals {
  repository_root     = abspath("${path.module}/../..")
  image_manage_script = "${path.module}/scripts/manage_lambda_images.sh"
  image_manage_file   = "infra/aws/scripts/manage_lambda_images.sh"

  ingestion_image_files = sort(concat(
    [
      "services/api/.dockerignore",
      "services/api/src/functions/ingestion/Dockerfile",
      "services/api/requirements-ingestion.txt",
      local.image_manage_file,
    ],
    [
      for file_name in fileset("${local.repository_root}/services/api/src", "**") :
      "services/api/src/${file_name}"
    ],
  ))

  database_migration_image_files = sort(concat(
    [
      ".dockerignore",
      "services/api/src/functions/database_migration/Dockerfile",
      "services/api/requirements-database-tools.txt",
      local.image_manage_file,
    ],
    [
      for file_name in fileset("${local.repository_root}/services/api/src/functions/database_migration", "**/*.py") :
      "services/api/src/functions/database_migration/${file_name}"
    ],
    [
      for file_name in fileset("${local.repository_root}/packages/database/migrations", "*.sql") :
      "packages/database/migrations/${file_name}"
    ],
  ))

  rds_connectivity_image_files = sort(concat(
    [
      ".dockerignore",
      "services/api/src/functions/rds_connectivity/Dockerfile",
      "services/api/requirements-database-tools.txt",
      local.image_manage_file,
    ],
    [
      for file_name in fileset("${local.repository_root}/services/api/src/functions/rds_connectivity", "**/*.py") :
      "services/api/src/functions/rds_connectivity/${file_name}"
    ],
  ))

  route_search_image_files = sort(concat(
    [
      ".dockerignore",
      "services/api/src/functions/route_search/Dockerfile",
      "services/api/requirements-database-tools.txt",
      local.image_manage_file,
    ],
    flatten([
      for directory in ["clients", "common", "repositories", "scoring", "services"] :
      [
        for file_name in fileset("${local.repository_root}/services/api/src/${directory}", "**/*.py") :
        "services/api/src/${directory}/${file_name}"
      ]
    ]),
    [
      for file_name in fileset("${local.repository_root}/services/api/src/functions/route_search", "**/*.py") :
      "services/api/src/functions/route_search/${file_name}"
    ],
    [
      "services/api/src/functions/location_search/assets/city-of-melbourne-boundary-2022.geojson",
    ],
  ))

  refuge_search_image_files = sort(concat(
    [
      ".dockerignore",
      "services/api/src/functions/refuge_search/Dockerfile",
      "services/api/requirements-database-tools.txt",
      local.image_manage_file,
      "services/api/src/functions/location_search/assets/city-of-melbourne-boundary-2022.geojson",
    ],
    flatten([
      for directory in ["clients", "common", "repositories", "services"] :
      [
        for file_name in fileset("${local.repository_root}/services/api/src/${directory}", "**/*.py") :
        "services/api/src/${directory}/${file_name}"
      ]
    ]),
    [
      for file_name in fileset("${local.repository_root}/services/api/src/functions/refuge_search", "**/*.py") :
      "services/api/src/functions/refuge_search/${file_name}"
    ],
  ))

  ingestion_image_hash = sha256(join("", [
    for file_name in local.ingestion_image_files :
    "${file_name}:${filesha256("${local.repository_root}/${file_name}")}"
  ]))
  database_migration_image_hash = sha256(join("", [
    for file_name in local.database_migration_image_files :
    "${file_name}:${filesha256("${local.repository_root}/${file_name}")}"
  ]))
  rds_connectivity_image_hash = sha256(join("", [
    for file_name in local.rds_connectivity_image_files :
    "${file_name}:${filesha256("${local.repository_root}/${file_name}")}"
  ]))
  route_search_image_hash = sha256(join("", [
    for file_name in local.route_search_image_files :
    "${file_name}:${filesha256("${local.repository_root}/${file_name}")}"
  ]))
  refuge_search_image_hash = sha256(join("", [
    for file_name in local.refuge_search_image_files :
    "${file_name}:${filesha256("${local.repository_root}/${file_name}")}"
  ]))

  ingestion_image_tag          = "sha-${substr(local.ingestion_image_hash, 0, 20)}"
  database_migration_image_tag = "sha-${substr(local.database_migration_image_hash, 0, 20)}"
  rds_connectivity_image_tag   = "sha-${substr(local.rds_connectivity_image_hash, 0, 20)}"
  route_search_image_tag       = "sha-${substr(local.route_search_image_hash, 0, 20)}"
  refuge_search_image_tag      = "sha-${substr(local.refuge_search_image_hash, 0, 20)}"

  ingestion_image_uri          = "${aws_ecr_repository.ingestion.repository_url}@${data.aws_ecr_image.ingestion.image_digest}"
  database_migration_image_uri = "${aws_ecr_repository.database_migration.repository_url}@${data.aws_ecr_image.database_migration.image_digest}"
  rds_connectivity_image_uri   = "${aws_ecr_repository.rds_connectivity.repository_url}@${data.aws_ecr_image.rds_connectivity.image_digest}"
  route_search_image_uri       = "${aws_ecr_repository.route_search.repository_url}@${data.aws_ecr_image.route_search.image_digest}"
  refuge_search_image_uri      = "${aws_ecr_repository.refuge_search.repository_url}@${data.aws_ecr_image.refuge_search.image_digest}"
}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

resource "aws_ecr_repository" "ingestion" {
  name                 = "${local.name_prefix}-ingestion"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_repository" "database_migration" {
  name                 = "${local.name_prefix}-database-migration"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_repository" "rds_connectivity" {
  name                 = "${local.name_prefix}-rds-connectivity"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_repository" "route_search" {
  name                 = "${local.name_prefix}-route-search"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_repository" "refuge_search" {
  name                 = "${local.name_prefix}-refuge-search"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_repository_policy" "lambda_pull" {
  for_each = {
    ingestion          = aws_ecr_repository.ingestion.name
    database_migration = aws_ecr_repository.database_migration.name
    rds_connectivity   = aws_ecr_repository.rds_connectivity.name
    route_search       = aws_ecr_repository.route_search.name
    refuge_search      = aws_ecr_repository.refuge_search.name
  }

  repository = each.value
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "LambdaImagePull"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = [
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
      ]
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
        ArnLike = {
          "aws:SourceArn" = "arn:${data.aws_partition.current.partition}:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-*"
        }
      }
    }]
  })
}

resource "aws_ecr_lifecycle_policy" "lambda_images" {
  for_each = {
    ingestion          = aws_ecr_repository.ingestion.name
    database_migration = aws_ecr_repository.database_migration.name
    rds_connectivity   = aws_ecr_repository.rds_connectivity.name
    route_search       = aws_ecr_repository.route_search.name
    refuge_search      = aws_ecr_repository.refuge_search.name
  }

  repository = each.value
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Retain the five newest Lambda images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = {
        type = "expire"
      }
    }]
  })
}

resource "terraform_data" "lambda_images" {
  count = var.build_lambda_images ? 1 : 0

  triggers_replace = [
    local.ingestion_image_hash,
    local.database_migration_image_hash,
    local.rds_connectivity_image_hash,
    local.route_search_image_hash,
    local.refuge_search_image_hash,
    aws_ecr_repository.ingestion.repository_url,
    aws_ecr_repository.database_migration.repository_url,
    aws_ecr_repository.rds_connectivity.repository_url,
    aws_ecr_repository.route_search.repository_url,
    aws_ecr_repository.refuge_search.repository_url,
  ]

  provisioner "local-exec" {
    command = "bash \"${local.image_manage_script}\" publish-all"

    environment = {
      AWS_REGION                        = var.aws_region
      INGESTION_REPOSITORY_URL          = aws_ecr_repository.ingestion.repository_url
      INGESTION_IMAGE_TAG               = local.ingestion_image_tag
      DATABASE_MIGRATION_REPOSITORY_URL = aws_ecr_repository.database_migration.repository_url
      DATABASE_MIGRATION_IMAGE_TAG      = local.database_migration_image_tag
      RDS_CONNECTIVITY_REPOSITORY_URL   = aws_ecr_repository.rds_connectivity.repository_url
      RDS_CONNECTIVITY_IMAGE_TAG        = local.rds_connectivity_image_tag
      ROUTE_SEARCH_REPOSITORY_URL       = aws_ecr_repository.route_search.repository_url
      ROUTE_SEARCH_IMAGE_TAG            = local.route_search_image_tag
      REFUGE_SEARCH_REPOSITORY_URL      = aws_ecr_repository.refuge_search.repository_url
      REFUGE_SEARCH_IMAGE_TAG           = local.refuge_search_image_tag
    }
  }
}

data "aws_ecr_image" "ingestion" {
  repository_name = aws_ecr_repository.ingestion.name
  image_tag       = local.ingestion_image_tag

  depends_on = [terraform_data.lambda_images]
}

data "aws_ecr_image" "database_migration" {
  repository_name = aws_ecr_repository.database_migration.name
  image_tag       = local.database_migration_image_tag

  depends_on = [terraform_data.lambda_images]
}

data "aws_ecr_image" "rds_connectivity" {
  repository_name = aws_ecr_repository.rds_connectivity.name
  image_tag       = local.rds_connectivity_image_tag

  depends_on = [terraform_data.lambda_images]
}

data "aws_ecr_image" "route_search" {
  repository_name = aws_ecr_repository.route_search.name
  image_tag       = local.route_search_image_tag

  depends_on = [terraform_data.lambda_images]
}

data "aws_ecr_image" "refuge_search" {
  repository_name = aws_ecr_repository.refuge_search.name
  image_tag       = local.refuge_search_image_tag

  depends_on = [terraform_data.lambda_images]
}
