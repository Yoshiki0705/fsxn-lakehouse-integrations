output "storage_credential_id" {
  description = "Databricks Storage Credential ID"
  value       = databricks_storage_credential.fsxn.id
}

output "external_location_root_url" {
  description = "External Location URL (root)"
  value       = databricks_external_location.fsxn_root.url
}

output "external_location_bronze_url" {
  description = "External Location URL (bronze)"
  value       = databricks_external_location.fsxn_bronze.url
}

output "external_location_silver_url" {
  description = "External Location URL (silver)"
  value       = databricks_external_location.fsxn_silver.url
}

output "external_location_gold_url" {
  description = "External Location URL (gold)"
  value       = databricks_external_location.fsxn_gold.url
}

output "catalog_name" {
  description = "Unity Catalog name"
  value       = databricks_catalog.fsxn.name
}

output "cluster_policy_id" {
  description = "Cluster Policy ID for FSx for ONTAP access"
  value       = databricks_cluster_policy.fsxn_access.id
}
