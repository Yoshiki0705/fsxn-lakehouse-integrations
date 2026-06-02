# Snowflake External Stage with FSx for ONTAP S3 Access Point

🌐 [日本語](external-stage-fsx-s3ap-validation-ja.md) | English

## Purpose

Document the validated configuration for using FSx for ONTAP S3 Access Point alias as a Snowflake External Stage.

## Status: ✅ Verified (2026-05-31)

External Stage creation and LIST/SELECT operations work with FSx for ONTAP S3 Access Point alias. TO_FILE operation is an Engineering WIP.

## Configuration

### Storage Integration

```sql
CREATE OR REPLACE STORAGE INTEGRATION fsxn_s3ap_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/fsxn-snowflake-verification-role'
  STORAGE_ALLOWED_LOCATIONS = ('s3://verification-tes-fpg5t76dgh3xchkrudk6yc4jhgzz1apn1b-ext-s3alias/');
```

### External Stage

```sql
CREATE OR REPLACE STAGE fsxn_external_stage
  STORAGE_INTEGRATION = fsxn_s3ap_integration
  URL = 's3://verification-tes-fpg5t76dgh3xchkrudk6yc4jhgzz1apn1b-ext-s3alias/'
  FILE_FORMAT = (TYPE = 'CSV');
```

### Verified Operations

```sql
-- LIST files on FSx via S3 AP
LIST @fsxn_external_stage;
-- ✅ Returns file listing

-- SELECT from staged files
SELECT $1, $2 FROM @fsxn_external_stage/path/to/file.csv;
-- ✅ Returns file content

-- COPY INTO Snowflake table
COPY INTO target_table FROM @fsxn_external_stage/path/to/file.csv;
-- ✅ Works for supported file formats
```

### Known Limitation: TO_FILE

```sql
-- COPY FILES (TO_FILE) from S3 AP
COPY FILES INTO @another_stage FROM @fsxn_external_stage;
-- ⚠️ Engineering WIP — not yet supported for S3 AP paths
```

## IAM Policy Requirements

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:ap-northeast-1:<ACCOUNT_ID>:accesspoint/verification-tes-fpg5t76dgh3xchkrudk6yc4jhgzz1apn1b",
        "arn:aws:s3:ap-northeast-1:<ACCOUNT_ID>:accesspoint/verification-tes-fpg5t76dgh3xchkrudk6yc4jhgzz1apn1b/*"
      ]
    }
  ]
}
```

## S3 Access Point Policy

The S3 Access Point must allow the Snowflake IAM role to perform the required S3 operations.

## Important Notes

- This validation uses the S3 AP **alias** (not ARN) in the URL
- Standard Snowflake documentation uses `s3://bucket-name/` format; S3 AP alias works as a bucket-name substitute
- FSx for ONTAP S3 AP provides read access to NFS/SMB volumes via S3 protocol
- File-system identity associated with the S3 AP determines which files are accessible
- Tested in ap-northeast-1 region on 2026-05-31

## References

- [Snowflake: External stages](https://docs.snowflake.com/en/sql-reference/sql/create-stage)
- [Snowflake: Storage integrations](https://docs.snowflake.com/en/sql-reference/sql/create-storage-integration)
- [AWS: FSx for ONTAP S3 Access Points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-access-points.html)
