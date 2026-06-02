"""
external-catalog-setup.py — Databricks External Catalog Configuration

Configures Databricks Unity Catalog to access the S3 Tables Iceberg metadata
table via the Iceberg REST endpoint.

This enables Databricks users to query the metadata catalog using Spark SQL
without data movement.

Prerequisites:
    - Databricks workspace with Unity Catalog enabled
    - IAM role with s3tables:* permissions (cross-account if needed)
    - Databricks CLI configured (or run in a notebook)

Usage:
    # As a Databricks notebook (recommended):
    # Copy the SQL cells below into a Databricks SQL notebook

    # Or via Databricks CLI:
    # databricks unity-catalog external-locations create ...
"""

# =============================================================================
# Databricks SQL — External Catalog Setup
# =============================================================================
#
# Run these SQL statements in a Databricks SQL notebook or SQL warehouse.
#

SETUP_SQL = """
-- ==========================================================================
-- Step 1: Create External Connection (Iceberg REST Catalog)
-- ==========================================================================
-- Note: This requires Databricks Unity Catalog with External Catalog support.
-- The connection points to the S3 Tables Iceberg REST endpoint.

CREATE CONNECTION IF NOT EXISTS fsxn_metadata_catalog
TYPE iceberg_rest
OPTIONS (
  uri = 'https://s3tables.ap-northeast-1.amazonaws.com/iceberg',
  warehouse = 'arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog',
  'rest.sigv4-enabled' = 'true',
  'rest.signing-region' = 'ap-northeast-1',
  'rest.signing-name' = 's3tables'
);

-- ==========================================================================
-- Step 2: Create Foreign Catalog
-- ==========================================================================
-- This makes the S3 Tables metadata visible in Unity Catalog's namespace.

CREATE FOREIGN CATALOG IF NOT EXISTS fsxn_metadata
USING CONNECTION fsxn_metadata_catalog;

-- ==========================================================================
-- Step 3: Verify Access
-- ==========================================================================
-- List available namespaces and tables

SHOW SCHEMAS IN fsxn_metadata;
SHOW TABLES IN fsxn_metadata.metadata;

-- ==========================================================================
-- Step 4: Query Metadata
-- ==========================================================================

-- File type distribution
SELECT
    file_type,
    COUNT(*) AS count,
    SUM(file_size) / 1024 / 1024 / 1024 AS total_gb
FROM fsxn_metadata.metadata.unstructured_files
WHERE is_deleted = false
GROUP BY file_type
ORDER BY total_gb DESC;

-- Search by classification
SELECT
    file_name,
    file_path,
    classification,
    confidence_score,
    summary
FROM fsxn_metadata.metadata.unstructured_files
WHERE classification = 'contract'
  AND confidence_score >= 0.7
  AND is_deleted = false
ORDER BY confidence_score DESC
LIMIT 20;

-- PII files requiring attention
SELECT
    file_name,
    file_type,
    sensitivity_level,
    anonymization_status
FROM fsxn_metadata.metadata.unstructured_files
WHERE has_pii = true
  AND is_deleted = false;
"""

# =============================================================================
# Databricks Python — Vector Search Integration
# =============================================================================

VECTOR_SEARCH_SETUP = """
# ==========================================================================
# Mosaic AI Vector Search — Sync embeddings from metadata table
# ==========================================================================
# This creates a Vector Search index from the embedding_vector column,
# enabling similarity search directly in Databricks.

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Create Vector Search endpoint (if not exists)
# Note: Vector Search endpoints have a minimum cost — use shared endpoint if available
endpoint_name = "fsxn-metadata-search"

# Create index from the metadata table
# The index syncs embeddings from the Iceberg table
index_name = "fsxn_metadata.metadata.unstructured_files_index"

# Delta Sync Index configuration
# Note: Requires the source table to be accessible as a Delta table or via
# the Foreign Catalog. If Foreign Catalog doesn't support Vector Search sync,
# use a scheduled job to copy embeddings to a Delta table first.

# Alternative: Direct Index (manual sync)
# This approach works regardless of source table format:

import struct
import base64

# Read embeddings from metadata table
embeddings_df = spark.sql('''
    SELECT
        file_id,
        file_name,
        file_path,
        file_type,
        classification,
        summary,
        embedding_vector
    FROM fsxn_metadata.metadata.unstructured_files
    WHERE embedding_vector IS NOT NULL
      AND is_deleted = false
      AND enrichment_status = 'completed'
''')

# Decode binary embeddings to float arrays
from pyspark.sql.functions import udf
from pyspark.sql.types import ArrayType, FloatType

@udf(returnType=ArrayType(FloatType()))
def decode_embedding(binary_data):
    if binary_data is None:
        return None
    floats = struct.unpack(f'{len(binary_data)//4}f', bytes(binary_data))
    return list(floats)

embeddings_decoded = embeddings_df.withColumn(
    "embedding_array", decode_embedding("embedding_vector")
)

# Write to a Delta table for Vector Search sync
embeddings_decoded.select(
    "file_id", "file_name", "file_path", "file_type",
    "classification", "summary", "embedding_array"
).write.mode("overwrite").saveAsTable("fsxn_metadata_vectors")

# Create Vector Search index on the Delta table
# (Run via Databricks UI or SDK)
print("Delta table 'fsxn_metadata_vectors' created.")
print("Create Vector Search index via Databricks UI:")
print("  Catalog: default")
print("  Table: fsxn_metadata_vectors")
print("  Embedding column: embedding_array")
print("  Embedding dimension: 1024")
"""

if __name__ == "__main__":
    print("=" * 60)
    print("Databricks External Catalog Setup for S3 Tables Metadata")
    print("=" * 60)
    print()
    print("Run the following SQL in a Databricks SQL notebook:")
    print()
    print(SETUP_SQL)
    print()
    print("=" * 60)
    print("Vector Search Integration (optional):")
    print("=" * 60)
    print()
    print(VECTOR_SEARCH_SETUP)
