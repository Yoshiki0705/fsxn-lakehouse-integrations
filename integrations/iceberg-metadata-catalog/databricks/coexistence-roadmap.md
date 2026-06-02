# Databricks + AWS Coexistence Roadmap

🌐 [日本語](coexistence-roadmap-ja.md) | English

## Purpose

Phased integration plan for organizations using both AWS-native analytics (Athena, Lake Formation) and Databricks (Unity Catalog, SQL, ML).

## Phases

### Phase 1: AWS-Native Metadata Catalog (Current)

```
FSx for ONTAP → S3 AP → Lambda/Bedrock → S3 Tables (Iceberg)
                                              │
                                    ┌─────────┼─────────┐
                                    ▼         ▼         ▼
                              Athena ✅   OpenSearch  Lake Formation
```

- **Status**: ✅ Verified
- **Governance**: Lake Formation (table-level)
- **Search**: OpenSearch Serverless NextGen (kNN)
- **Cost**: ~$114/month at 100K files

### Phase 2: Databricks Metadata Activation

```
S3 Tables (Iceberg) ──PyIceberg export──→ S3 (Parquet/Delta)
                                              │
                                              ▼
                                    UC External Location
                                              │
                                              ▼
                                    Databricks SQL / AI BI
```

- **Status**: Available now (no platform dependency)
- **Governance**: Unity Catalog grants on synced table
- **Use cases**: Dashboards, AI/BI Genie, ML features, operational reporting
- **Tradeoff**: Metadata copy (small, ~MB scale); raw files remain zero-copy

### Phase 3: UC Foreign Catalog Validation

```
S3 Tables (Iceberg) ←──Glue Iceberg REST──→ UC Foreign Catalog
                                              │
                                              ▼
                                    Databricks SQL / Spark
                                    (read-only, REFRESH required)
```

- **Status**: 🔄 Pending validation (B-4/B-5)
- **Governance**: UC governance on foreign tables
- **Advantage**: No data copy, no format conversion
- **Limitation**: Read-only, no auto-refresh, no credential vending

### Phase 4: Databricks-First Option (If Applicable)

```
FSx for ONTAP → DataSync → S3 → UC Managed Iceberg / Delta + UniForm
                                              │
                                    ┌─────────┼─────────┐
                                    ▼         ▼         ▼
                              Databricks   Athena    External
                              SQL/Spark    (via Glue  Iceberg
                                           federation) clients
```

- **Status**: Architectural option (not validated in this PoC)
- **Governance**: Unity Catalog (primary) + Glue federation for AWS engines
- **Best for**: Organizations standardizing on Databricks as primary platform
- **Tradeoff**: Requires DataSync for raw file ingestion; UC is authoritative catalog

## Decision Criteria

| Factor | AWS-First (Phase 1-2) | Databricks-First (Phase 4) |
|---|---|---|
| Primary query engine | Athena | Databricks SQL |
| Primary governance | Lake Formation | Unity Catalog |
| Lineage/Discovery | Glue Data Catalog | UC Explorer |
| ML/AI platform | SageMaker / Bedrock | Databricks ML / MLflow |
| Cost model | Pay-per-query (Athena) | DBU-based (Databricks) |
| Raw file access | S3 AP (direct) | DataSync → S3 → UC |
| Cross-platform | Iceberg REST (open) | UC Iceberg REST + Glue federation |

## Recommended Starting Point

1. **Start with Phase 1** (AWS-native) — lowest barrier, fully verified
2. **Add Phase 2** when Databricks BI/ML is needed — no platform dependency
3. **Validate Phase 3** when Databricks support confirms UC Foreign Catalog compatibility
4. **Consider Phase 4** only if organization is standardizing on Databricks as primary platform

## References

- [AWS Glue → UC federation](https://docs.aws.amazon.com/lake-formation/latest/dg/catalog-federation-databricks.html)
- [Databricks → AWS Glue federation](https://docs.databricks.com/aws/en/query-federation/hms-federation-glue)
- [UC Foreign Iceberg validation plan](uc-foreign-iceberg-validation.md)
