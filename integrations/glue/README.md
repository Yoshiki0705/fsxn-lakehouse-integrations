# AWS Glue Integration

🚧 **Planned** — Crawler + ETL Job + Medallion Architecture

## Overview

Use AWS Glue for ETL pipelines with FSx for NetApp ONTAP as both
source and target storage via S3 Access Points.

## Architecture

```
FSxN (Raw) → S3 AP → Glue Crawler → Glue ETL Job → S3 AP → FSxN (Curated)
```

## Planned Content

- [ ] CloudFormation template (Glue Job + Crawler + S3 AP)
- [ ] Glue ETL scripts (PySpark)
- [ ] Medallion architecture implementation
- [ ] Data quality checks
- [ ] Documentation (JA/EN)
