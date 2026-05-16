variable "aws_region" {
  description = "AWS region where FSxN and S3 AP are deployed"
  type        = string
  default     = "ap-northeast-1"
}

variable "environment_name" {
  description = "Environment name prefix"
  type        = string
  default     = "fsxn-lakehouse"
}

variable "databricks_workspace_url" {
  description = "Databricks workspace URL (e.g., https://xxx.cloud.databricks.com)"
  type        = string
}

variable "databricks_account_id" {
  description = "Databricks account ID"
  type        = string
}

variable "s3_access_point_alias" {
  description = "S3 Access Point alias (from CloudFormation output)"
  type        = string
}

variable "s3_access_point_arn" {
  description = "S3 Access Point ARN (from CloudFormation output)"
  type        = string
}

variable "iam_role_arn" {
  description = "IAM Role ARN for Databricks (from CloudFormation output)"
  type        = string
}

variable "catalog_name" {
  description = "Unity Catalog name for FSxN external data"
  type        = string
  default     = "fsxn_lakehouse"
}

variable "schema_name" {
  description = "Default schema name"
  type        = string
  default     = "default"
}

variable "metastore_id" {
  description = "Unity Catalog Metastore ID"
  type        = string
}
