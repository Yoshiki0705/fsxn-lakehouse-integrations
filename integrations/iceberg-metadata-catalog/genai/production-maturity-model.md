# Production Maturity Model

## Overview

A phased approach to deploying the AI-powered metadata catalog, from minimal viable catalog to full business workflow integration.

## Maturity Levels

| Level | Name | Scope | AI Involvement | Governance | Cost Profile |
|:-----:|------|-------|----------------|------------|-------------|
| 1 | **Metadata Scan Only** | File inventory (path, size, type, timestamps) | None | Lake Formation table-level | ~$5/month |
| 2 | **AI Enrichment (Selective)** | Classification + embeddings for selected file types | Bedrock Vision + Titan Embeddings | + Athena Views | ~$40-100/month |
| 3 | **Human Review Workflow** | Low-confidence queue, PII review, approval pipeline | + PII detection + confidence scoring | + Row-level filtering | ~$100-200/month |
| 4 | **Governed Search / BI Activation** | OpenSearch kNN, Snowflake/Databricks integration | + Vector search + multi-engine access | + Horizon/UC policies | ~$200-400/month |
| 5 | **Business Workflow Integration** | AI assistant, automated routing, approval workflows | + Agentic AI + tool execution | + Full audit + human-in-the-loop | Custom |

## Level 1: Metadata Scan Only

**Goal**: Make files discoverable via SQL without any AI processing.

- Deploy S3 Tables + Iceberg metadata table
- Run initial ListObjectsV2 scan via Lambda
- Query via Athena (`SELECT * WHERE file_name LIKE '%invoice%'`)
- Lake Formation table-level governance

**Entry criteria**: FSx for ONTAP with S3 Access Point configured.
**Exit criteria**:
- 95%+ files in target volume inventoried
- Latest-record view available and validated
- Basic Athena query returns correct results
- Lake Formation table-level grant/revoke tested

## Level 2: AI Enrichment (Selective)

**Goal**: Automatically classify high-value file types.

- Enable Bedrock Claude Vision for images
- Enable Titan Embeddings for all classified files
- Track enrichment_status (pending / completed / failed)
- Evaluate classification accuracy on labeled sample

**Entry criteria**: Level 1 complete + Bedrock access enabled.
**Exit criteria**:
- Selected file types enriched (images, PDFs, or configured types)
- Classification accuracy >80% on labeled sample
- Model/prompt version recorded in metadata
- Failed enrichment retry queue available and operational
- Error rate <5%

## Level 3: Human Review Workflow

**Goal**: Ensure AI classifications meet business accuracy standards.

- Low-confidence queue (confidence < 0.7 → human review)
- PII detection with review pipeline
- Periodic spot-check for high-confidence results
- Business owner approval workflow

**Entry criteria**: Level 2 complete + defined accuracy targets.
**Exit criteria**:
- Human review workflow operational (queue → review → approve/reject)
- False positive / false negative rates measured and documented
- Business owner approval process defined and tested
- PII detection false negative rate <5% on representative sample

## Level 4: Governed Search / BI Activation

**Goal**: Make metadata accessible to business users via their preferred tools.

- OpenSearch Serverless NextGen (vector + lexical search)
- Snowflake integration (Glue REST + VENDED_CREDENTIALS or metadata sync)
- Databricks integration (when UC Foreign Catalog available, or metadata sync to Delta)
- Snowflake Horizon / UC governance policies applied

**Entry criteria**: Level 3 complete + search quality validated.
**Exit criteria**:
- Governed search exposed to business users on their primary platform
- PII/path-sensitive views separated from general access
- Audit evidence retained for all metadata access
- Search relevance (nDCG@5) meets defined threshold

## Level 5: Business Workflow Integration

**Goal**: Metadata catalog drives business actions, not just discovery.

- AI assistant (Bedrock Agents) answers questions about files
- Automated routing (new sensitive file → security review queue)
- Approval workflows (data access request → owner approval → time-bound grant)
- Cross-department collaboration via governed metadata sharing

**Entry criteria**: Level 4 complete + business workflows defined.
**Exit criteria**:
- Integrated with at least one business workflow (search, routing, or approval)
- KPI improvement measured (discovery time, compliance coverage, or audit readiness)
- Operational ownership transferred to designated team
- Cost model validated against actual usage

## Progression Guidance

- **Start small**: Level 1 can be deployed in a single day ($0.07 demo cost)
- **Iterate on value**: Each level adds measurable business value before proceeding
- **Don't skip human review**: Level 3 is critical for trust and regulatory acceptance
- **Plan costs incrementally**: Each level's cost is additive but predictable
