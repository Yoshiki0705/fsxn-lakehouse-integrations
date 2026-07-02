🌐 **English** | [日本語](README-ja.md)

# Module 07: Enterprise Governance (Lake Formation)

## Overview

Add fine-grained access control to FSx for ONTAP S3 AP data using AWS Lake Formation. Same governance applies to Athena, Redshift Spectrum, and EMR simultaneously.

```
Lake Formation (table/column/row/tag permissions)
        │
        ├── Athena queries → governed
        ├── Redshift Spectrum queries → governed
        └── EMR Spark reads → governed
        
All sharing the same Glue Catalog + Lake Formation permissions
```

## Prerequisites

- Glue Catalog table pointing to FSx for ONTAP S3 AP (from Module 02)
- IAM user/role with Lake Formation admin permissions

## Steps

### 1. Set Lake Formation Admin

```bash
aws lakeformation put-data-lake-settings \
  --data-lake-settings '{
    "DataLakeAdmins": [{"DataLakePrincipalIdentifier": "arn:aws:iam::<ACCOUNT>:user/<ADMIN>"}]
  }'
```

### 2. Grant Table-Level Permission

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier": "arn:aws:iam::<ACCOUNT>:role/<ANALYST_ROLE>"}' \
  --resource '{"Table": {"DatabaseName": "fsxn_poc", "Name": "sensor_data"}}' \
  --permissions '["SELECT", "DESCRIBE"]'
```

### 3. Column-Level Permission (restrict specific columns)

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier": "arn:aws:iam::<ACCOUNT>:role/<RESTRICTED_ROLE>"}' \
  --resource '{"TableWithColumns": {"DatabaseName": "fsxn_poc", "Name": "sensor_data", "ColumnNames": ["device_id", "temperature", "status"]}}' \
  --permissions '["SELECT"]'
```

### 4. Row Filter (Data Cells Filter)

```bash
aws lakeformation create-data-cells-filter \
  --table-data '{
    "TableCatalogId": "<ACCOUNT>",
    "DatabaseName": "fsxn_poc",
    "TableName": "sensor_data",
    "Name": "normal_only",
    "RowFilter": {"FilterExpression": "status = '\''normal'\''"},
    "ColumnNames": ["device_id", "timestamp", "temperature", "status"]
  }'
```

### 5. LF-Tag (Tag-Based Access Control)

```bash
# Create tag
aws lakeformation create-lf-tag --tag-key sensitivity --tag-values '["public","internal","confidential"]'

# Assign tag to table
aws lakeformation add-lf-tags-to-resource \
  --resource '{"Table": {"DatabaseName": "fsxn_poc", "Name": "sensor_data"}}' \
  --lf-tags '[{"TagKey": "sensitivity", "TagValues": ["internal"]}]'

# Grant access by tag
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier": "arn:aws:iam::<ACCOUNT>:role/<ROLE>"}' \
  --resource '{"LFTagPolicy": {"ResourceType": "TABLE", "Expression": [{"TagKey": "sensitivity", "TagValues": ["public", "internal"]}]}}' \
  --permissions '["SELECT", "DESCRIBE"]'
```

## Verification

```sql
-- As restricted role, query should only return permitted columns/rows
SELECT device_id, temperature, status FROM fsxn_poc.sensor_data LIMIT 10;

-- Denied column should fail
SELECT humidity FROM fsxn_poc.sensor_data;  -- Error: column cannot be resolved
```

## Key Insight

Lake Formation permissions apply to **both Athena and Redshift Spectrum** simultaneously. Configure once, govern everywhere.

## Cost

Lake Formation itself is **free** — no additional charge beyond the underlying services (Athena, Glue Catalog).
