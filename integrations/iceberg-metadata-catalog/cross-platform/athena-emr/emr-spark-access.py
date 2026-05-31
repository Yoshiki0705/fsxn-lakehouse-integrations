"""
emr-spark-access.py — EMR Spark access to S3 Tables Iceberg Metadata

Demonstrates reading the Iceberg metadata table from EMR Serverless Spark
using the S3 Tables Iceberg REST endpoint.

Usage (EMR Serverless):
    aws emr-serverless start-job-run \
      --application-id <APP_ID> \
      --execution-role-arn <ROLE_ARN> \
      --job-driver '{
        "sparkSubmit": {
          "entryPoint": "s3://<BUCKET>/scripts/emr-spark-access.py",
          "sparkSubmitParameters": "--conf spark.jars.packages=org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0 --conf spark.sql.catalog.s3tables=org.apache.iceberg.spark.SparkCatalog --conf spark.sql.catalog.s3tables.catalog-impl=org.apache.iceberg.rest.RESTCatalog --conf spark.sql.catalog.s3tables.uri=https://s3tables.ap-northeast-1.amazonaws.com/iceberg --conf spark.sql.catalog.s3tables.warehouse=arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog --conf spark.sql.catalog.s3tables.rest.sigv4-enabled=true --conf spark.sql.catalog.s3tables.rest.signing-region=ap-northeast-1 --conf spark.sql.catalog.s3tables.rest.signing-name=s3tables"
        }
      }'

Prerequisites:
    - EMR Serverless application (Spark 3.5+)
    - IAM role with s3tables:* and s3:* permissions on table bucket
    - Iceberg Spark runtime JAR
"""

from pyspark.sql import SparkSession


def main():
    # Initialize Spark with S3 Tables Iceberg catalog
    spark = (
        SparkSession.builder
        .appName("FSxN Metadata Catalog - EMR Access")
        .config("spark.sql.catalog.s3tables", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.s3tables.catalog-impl", "org.apache.iceberg.rest.RESTCatalog")
        .config("spark.sql.catalog.s3tables.uri", "https://s3tables.ap-northeast-1.amazonaws.com/iceberg")
        .config("spark.sql.catalog.s3tables.warehouse", "arn:aws:s3tables:ap-northeast-1:178625946981:bucket/fsxn-metadata-catalog")
        .config("spark.sql.catalog.s3tables.rest.sigv4-enabled", "true")
        .config("spark.sql.catalog.s3tables.rest.signing-region", "ap-northeast-1")
        .config("spark.sql.catalog.s3tables.rest.signing-name", "s3tables")
        .getOrCreate()
    )

    # =========================================================================
    # Query 1: File type distribution
    # =========================================================================
    print("=" * 60)
    print("File Type Distribution")
    print("=" * 60)

    df_types = spark.sql("""
        SELECT
            file_type,
            COUNT(*) AS count,
            SUM(file_size) / 1024 / 1024 / 1024 AS total_gb
        FROM s3tables.metadata.unstructured_files
        WHERE is_deleted = false
        GROUP BY file_type
        ORDER BY total_gb DESC
    """)
    df_types.show(20, truncate=False)

    # =========================================================================
    # Query 2: Search by classification
    # =========================================================================
    print("=" * 60)
    print("Contract Documents (confidence >= 0.7)")
    print("=" * 60)

    df_contracts = spark.sql("""
        SELECT
            file_name,
            file_path,
            confidence_score,
            summary
        FROM s3tables.metadata.unstructured_files
        WHERE classification = 'contract'
          AND confidence_score >= 0.7
          AND is_deleted = false
        ORDER BY confidence_score DESC
        LIMIT 20
    """)
    df_contracts.show(20, truncate=50)

    # =========================================================================
    # Query 3: Enrichment pipeline status
    # =========================================================================
    print("=" * 60)
    print("Enrichment Pipeline Status")
    print("=" * 60)

    df_status = spark.sql("""
        SELECT
            enrichment_status,
            COUNT(*) AS count,
            MIN(created_at) AS oldest,
            MAX(enriched_at) AS latest_enrichment
        FROM s3tables.metadata.unstructured_files
        WHERE is_deleted = false
        GROUP BY enrichment_status
    """)
    df_status.show()

    # =========================================================================
    # Query 4: PII files requiring anonymization
    # =========================================================================
    print("=" * 60)
    print("Files with PII (Anonymization Pending)")
    print("=" * 60)

    df_pii = spark.sql("""
        SELECT
            file_name,
            file_type,
            sensitivity_level,
            anonymization_status
        FROM s3tables.metadata.unstructured_files
        WHERE has_pii = true
          AND anonymization_status = 'pending'
          AND is_deleted = false
        ORDER BY created_at DESC
        LIMIT 20
    """)
    df_pii.show(20, truncate=False)

    # =========================================================================
    # Query 5: Time-travel (Iceberg snapshot)
    # =========================================================================
    print("=" * 60)
    print("Iceberg Table History (Snapshots)")
    print("=" * 60)

    df_history = spark.sql("""
        SELECT * FROM s3tables.metadata.unstructured_files.history
        ORDER BY made_current_at DESC
        LIMIT 10
    """)
    df_history.show(10, truncate=False)

    spark.stop()
    print("Done.")


if __name__ == "__main__":
    main()
