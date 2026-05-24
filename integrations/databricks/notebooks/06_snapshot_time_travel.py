# Experimental validation notebook
# This notebook documents observed behavior for FSx for ONTAP S3 Access Point access from Databricks.
# It is not a production reference architecture.
# Do not use Instance Profile + boto3 as a Unity Catalog governance replacement.

# Databricks notebook source
# MAGIC %md
# MAGIC # 06 - ONTAP Snapshot + Delta Time Travel
# MAGIC
# MAGIC Demonstrates the complementary use of ONTAP Snapshots and Delta Lake Time Travel
# MAGIC for comprehensive data protection and recovery on FSx for NetApp ONTAP.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Recovery Strategy Comparison
# MAGIC
# MAGIC | Aspect | Delta Time Travel | ONTAP Snapshot |
# MAGIC |--------|------------------|----------------|
# MAGIC | Granularity | Row-level | Volume-level |
# MAGIC | Scope | Single table | All tables on volume |
# MAGIC | Retention | Configurable (default 30 days) | Policy-based (hourly/daily/weekly) |
# MAGIC | Recovery Speed | Instant (read old version) | Instant (FlexClone) |
# MAGIC | Storage Cost | Delta log + old files | Block-level (only changed blocks) |
# MAGIC | Cross-table | No | Yes (consistent point-in-time) |
# MAGIC | Use Case | Undo bad UPDATE/DELETE | Disaster recovery, testing |

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

S3_ACCESS_POINT_ALIAS = "<your-s3ap-alias>"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Scenario 1: Delta Time Travel (Row-Level Recovery)

# COMMAND ----------

# MAGIC %sql
# MAGIC -- View Delta table history
# MAGIC DESCRIBE HISTORY fsxn_lakehouse.silver.orders;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Restore to previous version (undo accidental update)
# MAGIC -- RESTORE TABLE fsxn_lakehouse.silver.orders TO VERSION AS OF 0;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Query specific timestamp
# MAGIC -- SELECT * FROM fsxn_lakehouse.silver.orders TIMESTAMP AS OF '2024-06-01T00:00:00';

# COMMAND ----------

# MAGIC %md
# MAGIC ## Scenario 2: ONTAP Snapshot (Volume-Level Recovery)
# MAGIC
# MAGIC ### When to use ONTAP Snapshot over Delta Time Travel:
# MAGIC
# MAGIC 1. **Cross-table consistency**: Need to recover multiple related tables to same point
# MAGIC 2. **Beyond Delta retention**: Need data older than VACUUM retention
# MAGIC 3. **Metadata corruption**: Delta log itself is corrupted
# MAGIC 4. **Full volume recovery**: Disaster recovery scenario
# MAGIC 5. **Testing**: Clone production data for testing without copy

# COMMAND ----------

# MAGIC %md
# MAGIC ### ONTAP Snapshot Recovery Workflow
# MAGIC
# MAGIC ```bash
# MAGIC # 1. List available snapshots (via ONTAP CLI or REST API)
# MAGIC # ssh admin@fsxn-mgmt-ip
# MAGIC # volume snapshot show -vserver svm-lakehouse -volume vol_silver
# MAGIC #
# MAGIC # 2. Create FlexClone from snapshot
# MAGIC # volume clone create -vserver svm-lakehouse \
# MAGIC #   -flexclone vol_silver_recovery \
# MAGIC #   -parent-volume vol_silver \
# MAGIC #   -parent-snapshot daily.2024-06-01_0010
# MAGIC #
# MAGIC # 3. Create S3 bucket on clone volume (ONTAP CLI)
# MAGIC # vserver object-store-server bucket create \
# MAGIC #   -vserver svm-lakehouse \
# MAGIC #   -bucket silver-recovery \
# MAGIC #   -size 500GB
# MAGIC #
# MAGIC # 4. Create new S3 Access Point for recovery volume
# MAGIC # (via CloudFormation or AWS CLI)
# MAGIC #
# MAGIC # 5. Point Databricks External Location to recovery AP
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Scenario 3: FlexClone for Development/Testing

# COMMAND ----------

# MAGIC %md
# MAGIC ### Development Workflow with FlexClone
# MAGIC
# MAGIC ```
# MAGIC Production Volume (vol_silver)
# MAGIC │
# MAGIC ├── Snapshot: snap_before_migration
# MAGIC │   │
# MAGIC │   └── FlexClone: vol_silver_dev ──→ S3 AP (dev) ──→ Databricks (dev workspace)
# MAGIC │       • Zero additional storage
# MAGIC │       • Full read/write access
# MAGIC │       • Isolated from production
# MAGIC │       • Delete when done (instant)
# MAGIC │
# MAGIC └── Current production data ──→ S3 AP (prod) ──→ Databricks (prod workspace)
# MAGIC ```
# MAGIC
# MAGIC **Benefits:**
# MAGIC - Test schema migrations on real data without risk
# MAGIC - Validate ETL pipeline changes
# MAGIC - ML model training on production-scale data
# MAGIC - Performance testing with realistic data volumes

# COMMAND ----------

# Simulate: Read from a "cloned" location (same structure, different AP)
# In production, this would point to the FlexClone's S3 AP
DEV_AP_ALIAS = "<dev-s3ap-alias>"  # Would be the FlexClone's AP

# Example: Test a schema migration on cloned data
# df_dev = spark.read.format("delta").load(f"s3://{DEV_AP_ALIAS}/silver/orders_delta/")
# df_dev.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Scenario 4: Combined Recovery Matrix
# MAGIC
# MAGIC | Failure Type | Recovery Method | RTO |
# MAGIC |-------------|----------------|-----|
# MAGIC | Bad UPDATE/DELETE (single table) | Delta RESTORE | Seconds |
# MAGIC | Schema migration failure | Delta Time Travel | Seconds |
# MAGIC | Multiple table corruption | ONTAP Snapshot + FlexClone | Minutes |
# MAGIC | Volume-level failure | ONTAP Snapshot restore | Minutes |
# MAGIC | Region failure | SnapMirror failover | Minutes |
# MAGIC | Ransomware/malicious delete | ONTAP SnapLock + Snapshot | Minutes |
# MAGIC
# MAGIC ### Recommended Snapshot Policy for Lakehouse:
# MAGIC
# MAGIC ```
# MAGIC Hourly:  Keep 6 (covers intra-day issues)
# MAGIC Daily:   Keep 14 (covers 2 weeks of history)
# MAGIC Weekly:  Keep 8 (covers 2 months)
# MAGIC Monthly: Keep 12 (covers 1 year for compliance)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Automation: ONTAP REST API Integration

# COMMAND ----------

# Example: ONTAP REST API call to create snapshot (would run from Lambda/Step Functions)
import json

ontap_snapshot_request = {
    "method": "POST",
    "url": "https://<fsxn-mgmt-ip>/api/storage/volumes/<volume-uuid>/snapshots",
    "headers": {
        "Content-Type": "application/json",
        "Authorization": "Basic <base64-credentials>"
    },
    "body": {
        "name": "pre_etl_run_20240601",
        "comment": "Snapshot before daily ETL pipeline execution"
    }
}

print("ONTAP REST API - Create Snapshot:")
print(json.dumps(ontap_snapshot_request, indent=2))

# COMMAND ----------

# Example: ONTAP REST API call to create FlexClone
ontap_clone_request = {
    "method": "POST",
    "url": "https://<fsxn-mgmt-ip>/api/storage/volumes",
    "body": {
        "name": "vol_silver_dev_clone",
        "clone": {
            "parent_volume": {"name": "vol_silver"},
            "parent_snapshot": {"name": "pre_etl_run_20240601"},
            "is_flexclone": True
        },
        "svm": {"name": "svm-lakehouse"}
    }
}

print("ONTAP REST API - Create FlexClone:")
print(json.dumps(ontap_clone_request, indent=2))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC FSx for NetApp ONTAP provides enterprise-grade data protection that complements
# MAGIC Delta Lake's built-in time travel:
# MAGIC
# MAGIC 1. **Delta Time Travel** → Fine-grained, per-table row recovery
# MAGIC 2. **ONTAP Snapshot** → Volume-level, cross-table consistent recovery
# MAGIC 3. **FlexClone** → Zero-copy development/testing environments
# MAGIC 4. **SnapMirror** → Cross-region disaster recovery
# MAGIC 5. **SnapLock** → Immutable copies for compliance/ransomware protection
