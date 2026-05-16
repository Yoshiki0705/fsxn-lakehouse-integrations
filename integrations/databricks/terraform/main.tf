# =============================================================================
# Databricks Unity Catalog Integration with FSxN via S3 Access Point
# =============================================================================

# -----------------------------------------------------------------------------
# Storage Credential - IAM Role-based authentication
# -----------------------------------------------------------------------------
resource "databricks_storage_credential" "fsxn" {
  name    = "${var.environment_name}-fsxn-credential"
  comment = "Storage credential for FSx for NetApp ONTAP via S3 Access Point"

  aws_iam_role {
    role_arn = var.iam_role_arn
  }

  # Ensure the role trust policy is configured before creating credential
  depends_on = []
}

# -----------------------------------------------------------------------------
# External Location - Points to S3 Access Point
# -----------------------------------------------------------------------------
resource "databricks_external_location" "fsxn_root" {
  name            = "${var.environment_name}-fsxn-root"
  comment         = "FSxN root location via S3 Access Point"
  url             = "s3://${var.s3_access_point_alias}/"
  credential_name = databricks_storage_credential.fsxn.name

  # Skip validation if S3 AP is not yet accessible from Databricks network
  skip_validation = false
}

resource "databricks_external_location" "fsxn_bronze" {
  name            = "${var.environment_name}-fsxn-bronze"
  comment         = "FSxN Bronze layer (raw data)"
  url             = "s3://${var.s3_access_point_alias}/bronze/"
  credential_name = databricks_storage_credential.fsxn.name
  skip_validation = false
}

resource "databricks_external_location" "fsxn_silver" {
  name            = "${var.environment_name}-fsxn-silver"
  comment         = "FSxN Silver layer (cleaned data)"
  url             = "s3://${var.s3_access_point_alias}/silver/"
  credential_name = databricks_storage_credential.fsxn.name
  skip_validation = false
}

resource "databricks_external_location" "fsxn_gold" {
  name            = "${var.environment_name}-fsxn-gold"
  comment         = "FSxN Gold layer (business-ready)"
  url             = "s3://${var.s3_access_point_alias}/gold/"
  credential_name = databricks_storage_credential.fsxn.name
  skip_validation = false
}

# -----------------------------------------------------------------------------
# Catalog for FSxN External Data
# -----------------------------------------------------------------------------
resource "databricks_catalog" "fsxn" {
  name    = var.catalog_name
  comment = "Catalog for FSx for NetApp ONTAP lakehouse data"

  properties = {
    purpose    = "fsxn-lakehouse"
    managed_by = "terraform"
  }
}

# -----------------------------------------------------------------------------
# Schema (Database) within the Catalog
# -----------------------------------------------------------------------------
resource "databricks_schema" "bronze" {
  catalog_name = databricks_catalog.fsxn.name
  name         = "bronze"
  comment      = "Bronze layer - raw ingested data from FSxN"

  properties = {
    data_layer = "bronze"
  }
}

resource "databricks_schema" "silver" {
  catalog_name = databricks_catalog.fsxn.name
  name         = "silver"
  comment      = "Silver layer - cleaned and transformed data"

  properties = {
    data_layer = "silver"
  }
}

resource "databricks_schema" "gold" {
  catalog_name = databricks_catalog.fsxn.name
  name         = "gold"
  comment      = "Gold layer - business-ready aggregates"

  properties = {
    data_layer = "gold"
  }
}

# -----------------------------------------------------------------------------
# Grants - Catalog level
# -----------------------------------------------------------------------------
resource "databricks_grants" "catalog" {
  catalog = databricks_catalog.fsxn.name

  grant {
    principal  = "account users"
    privileges = ["USE_CATALOG", "USE_SCHEMA"]
  }
}

# -----------------------------------------------------------------------------
# Cluster Policy - Ensure S3 AP access configuration
# -----------------------------------------------------------------------------
resource "databricks_cluster_policy" "fsxn_access" {
  name = "${var.environment_name}-fsxn-cluster-policy"

  definition = jsonencode({
    "spark_conf.spark.hadoop.fs.s3a.endpoint" : {
      "type" : "fixed",
      "value" : "s3.${var.aws_region}.amazonaws.com"
    },
    "spark_conf.spark.hadoop.fs.s3a.path.style.access" : {
      "type" : "fixed",
      "value" : "true"
    },
    "aws_attributes.instance_profile_arn" : {
      "type" : "allowlist",
      "values" : [var.iam_role_arn]
    }
  })
}
