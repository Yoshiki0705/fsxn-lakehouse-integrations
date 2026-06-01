# Apache Iceberg Spec vs AWS S3 Tables Service Behavior

## Purpose

This document clarifies the boundary between the open Apache Iceberg specification and AWS S3 Tables service-specific behavior. Readers should not assume that all Iceberg spec features are available or behave identically on S3 Tables.

## Comparison

| Area | Apache Iceberg Spec | AWS S3 Tables Behavior |
|------|--------------------|-----------------------|
| **Table format** | Open spec (format-version 1 and 2) | Managed Iceberg table buckets (format-version 2) |
| **Catalog API** | REST Catalog specification (open) | S3 Tables REST endpoint + AWS Glue Iceberg REST endpoint |
| **Governance** | Not defined by Iceberg spec | IAM + Lake Formation (AWS-specific) |
| **Table maintenance** | Engine/catalog dependent (Spark, Trino, etc.) | S3 Tables service-managed auto-compaction |
| **Snapshot expiration** | Explicit via engine (e.g., Spark `expire_snapshots`) | Verify S3 Tables service-managed policies |
| **Manifest rewrite** | Explicit via engine | Verify S3 Tables auto-compaction scope |
| **Orphan file cleanup** | Explicit via engine | Verify service responsibility |
| **Primary key / uniqueness** | Not enforced by Iceberg | Not enforced — use dedup views |
| **Row-level deletes** | Position Delete Files (v2) | Supported via PyIceberg append of soft-delete records |
| **Schema evolution** | Supported by spec | Supported via PyIceberg / Glue |
| **Partition evolution** | Supported by spec | Verify via S3 Tables + Athena |
| **Time travel** | Supported by spec (snapshot-based) | Supported via Athena `$history` / `FOR TIMESTAMP AS OF` |
| **Naming constraints** | Spec allows mixed case | S3 Tables requires lowercase for AWS analytics integration |

## Implications for This Project

1. **Maintenance**: We cannot assume Spark-style `expire_snapshots` or `rewrite_manifests` procedures work on S3 Tables. Verify service-managed behavior.
2. **Governance**: Lake Formation integration is AWS-specific, not part of Iceberg spec.
3. **Naming**: Lowercase requirement is an S3 Tables / Glue / Athena constraint, not an Iceberg spec requirement.
4. **Deduplication**: Iceberg doesn't enforce uniqueness — our `latest_records.sql` view handles this at query time.

## References

- [Apache Iceberg Spec](https://iceberg.apache.org/spec/)
- [Iceberg REST Catalog Spec](https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml)
- [S3 Tables Documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables.html)
- [AWS Glue Iceberg REST Endpoint](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-glue-endpoint.html)
