# Minimal Repro: Unity Catalog External Location to FSx S3 AP

## Environment
- Workspace type: Customer-managed VPC
- DBR version: 17.3 LTS
- Access mode: Dedicated (Single User)
- Region: ap-northeast-1
- S3 AP ARN: `arn:aws:s3:<region>:<account>:accesspoint/<name>`
- S3 AP alias: `<name>-<hash>-ext-s3alias`

## Control test (should succeed)
1. Create Storage Credential with IAM role
2. Create External Location pointing to a regular S3 bucket
3. Run `dbutils.fs.ls("s3://<regular-bucket>/path/")`
4. Expected: success

## Repro test (demonstrates the boundary)
1. Use the same Storage Credential / IAM role
2. Create External Location pointing to FSx S3 AP alias
3. Run `dbutils.fs.ls("s3://<fsx-s3-ap-alias>/path/")`
4. Expected: AccessDenied with "no session policy allows s3:ListBucket"

## Key comparison
- Same IAM role
- Same permissions (s3:* on *)
- Different target: regular S3 bucket vs FSx S3 AP alias
- Regular bucket: succeeds
- FSx S3 AP: fails with session policy error

## Attachments to include
- Error stack trace (full AccessDenied message)
- IAM role policy document
- Storage credential configuration
- External location configuration (URL, credential reference)
- S3 AP ARN and alias
- Control test success evidence
