terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 5.75, < 7.0" }
  }
  backend "s3" {}
}
provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project      = "Baatchit"
      Environment  = var.environment
      Owner        = var.owner
      TeardownDate = var.teardown_date
      ManagedBy    = "Terraform"
    }
  }
}
