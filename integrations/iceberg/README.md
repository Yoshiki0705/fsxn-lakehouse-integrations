# Apache Iceberg Integration (Vendor-Neutral)

🚧 **Planned** — REST Catalog + S3 Access Point

## Overview

Vendor-neutral Apache Iceberg table management on FSx for NetApp ONTAP.
Uses REST Catalog for metadata management, accessible from any Iceberg-compatible engine.

## Architecture

```
Any Engine (Spark/Trino/Flink) → REST Catalog → S3 AP → FSxN Volume
```

## Planned Content

- [ ] CloudFormation template (REST Catalog on Lambda/ECS)
- [ ] Iceberg REST Catalog configuration
- [ ] Sample table creation scripts
- [ ] Multi-engine access examples
- [ ] Documentation (JA/EN)
