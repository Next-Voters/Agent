terraform {
  required_version = ">= 1.5"

  # Recommended for shared/production use: keep state in an encrypted, locked
  # remote backend rather than a local terraform.tfstate (state can contain
  # sensitive values). Bootstrap the bucket + lock table once, then uncomment:
  #
  # backend "s3" {
  #   bucket         = "next-voters-tfstate"
  #   key            = "infrastructure/terraform.tfstate"
  #   region         = "us-east-2"
  #   dynamodb_table = "next-voters-tflock"
  #   encrypt        = true
  # }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "next-voters"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
