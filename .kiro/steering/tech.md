---
inclusion: auto
---

# Technology Stack & Constraints

## Infrastructure as Code

- **CloudFormation (YAML)**: All AWS-native resources (FSxN, S3 AP, IAM, VPC, Lambda, Glue)
- **Terraform**: Vendor-specific resources only (Databricks Unity Catalog, Snowflake objects)
- **cfn-lint**: Required validation for all CloudFormation templates
- **terraform validate**: Required for all Terraform configs

## Languages & Runtimes

- **Python 3.12**: Scripts, Lambda functions, data generation, tests
- **Bash**: Setup scripts, automation
- **SQL**: Snowflake SQL, Athena SQL, Trino SQL, Spark SQL
- **HCL**: Terraform configurations

## FSxN S3 Access Points — Technical Constraints

### Supported S3 APIs
- GetObject, HeadObject, PutObject (single + multipart)
- DeleteObject, ListObjectsV2, CopyObject
- CreateMultipartUpload, UploadPart, CompleteMultipartUpload, AbortMultipartUpload

### NOT Supported
- S3 Event Notifications (use Lambda polling as workaround)
- S3 Select, S3 Inventory, S3 Batch Operations
- Object Lock (use SnapLock instead)
- Requester Pays

### Network Origin Requirements
- **Athena, Glue, Redshift Spectrum**: Require internet network origin
- **Databricks (customer VPC)**: Can use VPC network origin
- **Snowflake**: Uses internet network origin (PrivateLink optional)
- **EMR, Lambda**: Can use VPC network origin

### Access Point Configuration
- Attach to FSxN volume (not SVM-level bucket)
- Specify file access type: UNIX or Windows
- Specify username for access authorization
- One AP per volume per consumer (recommended)

## Data Formats

| Format | Primary Use | Table Format |
|--------|-------------|--------------|
| Parquet | Analytics (default) | External Table |
| Iceberg | ACID tables (vendor-neutral) | Managed/External |
| Delta Lake | ACID tables (Databricks) | Managed/External |
| CSV/JSON | Legacy ingestion | External Table |
| ORC | Hive compatibility | External Table |

## Testing Requirements

- pytest for Python unit tests
- cfn-lint for CloudFormation validation
- terraform validate for Terraform syntax
- Integration tests use boto3 against real S3 AP (not mocked)
- Screenshots captured during UI verification tasks

## Key Dependencies

```
boto3>=1.34.0
pandas>=2.2.0
pyarrow>=15.0.0
pytest>=8.0.0
cfn-lint>=0.87.0
```
