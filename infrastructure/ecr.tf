locals {
  ecr_lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countNumber = 7
          countUnit   = "days"
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = { type = "expire" }
      }
    ]
  })
}

resource "aws_ecr_repository" "pipeline" {
  name = "next-voters-${var.environment}-agent"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "pipeline" {
  repository = aws_ecr_repository.pipeline.name
  policy     = local.ecr_lifecycle_policy
}

resource "aws_ecr_repository" "dispatcher" {
  name = "next-voters-${var.environment}-dispatcher"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "dispatcher" {
  repository = aws_ecr_repository.dispatcher.name
  policy     = local.ecr_lifecycle_policy
}

resource "aws_ecr_repository" "email" {
  name = "next-voters-${var.environment}-email"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "email" {
  repository = aws_ecr_repository.email.name
  policy     = local.ecr_lifecycle_policy
}

resource "aws_ecr_repository" "worker" {
  name = "next-voters-${var.environment}-worker"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "worker" {
  repository = aws_ecr_repository.worker.name
  policy     = local.ecr_lifecycle_policy
}
