# Infrastructure for UK Crime Pipeline
# Provisions PostgreSQL on AWS RDS + S3 bucket for raw data

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# --- Variables ---

variable "aws_region" {
  default = "eu-west-2"  # London
}

variable "environment" {
  default = "dev"
}

variable "db_password" {
  sensitive = true
}

# --- S3 Bucket for raw crime data ---

resource "aws_s3_bucket" "raw_data" {
  bucket = "uk-crime-pipeline-${var.environment}-raw"
  tags = {
    Project     = "uk-crime-pipeline"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_versioning" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# --- RDS PostgreSQL ---

resource "aws_db_instance" "crime_db" {
  identifier        = "uk-crime-${var.environment}"
  engine            = "postgres"
  engine_version    = "16.3"
  instance_class    = "db.t3.micro"
  allocated_storage = 20

  db_name  = "crime_db"
  username = "analyst"
  password = var.db_password

  publicly_accessible    = false
  skip_final_snapshot    = true
  storage_encrypted      = true
  deletion_protection    = false
  backup_retention_period = 7

  tags = {
    Project     = "uk-crime-pipeline"
    Environment = var.environment
  }
}

# --- Outputs ---

output "s3_bucket" {
  value = aws_s3_bucket.raw_data.bucket
}

output "db_endpoint" {
  value = aws_db_instance.crime_db.endpoint
}

output "db_name" {
  value = aws_db_instance.crime_db.db_name
}
