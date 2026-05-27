🌐 **English** | [日本語](ja/discovery-questions.md)

# Discovery Questions — First Customer Meeting

## Purpose

Use these questions in the first meeting to determine the right PoC scope, engine selection, and governance requirements.

---

## 1. Current State

| # | Question | Why it matters |
|---|----------|---------------|
| 1 | What data is on your NAS today? (file types, volume, growth rate) | Determines sample data for PoC |
| 2 | How much data? (TB) | Impacts FSx throughput sizing |
| 3 | Who accesses it today? (NFS/SMB users, applications) | Ensures PoC doesn't disrupt existing workloads |
| 4 | Is the data structured (Parquet/CSV) or unstructured (images/PDFs/video)? | Determines engine selection |
| 5 | What analytics do you run today? (tools, frequency, latency requirements) | Baseline for improvement measurement |

## 2. Desired Outcome

| # | Question | Why it matters |
|---|----------|---------------|
| 6 | What question do you want to answer with this data? | Defines PoC success criteria |
| 7 | How quickly do you need answers? (real-time / hourly / daily) | Determines engine and refresh strategy |
| 8 | Who will consume the analytics? (data team / business users / AI systems) | Determines governance and access model |
| 9 | Do you need AI on this data? (summarize, search, classify, vision) | Determines Snowflake Cortex / Bedrock KB path |
| 10 | Do you need to share results with external partners/suppliers? | Determines Data Sharing path |

## 3. Platform & Governance

| # | Question | Why it matters |
|---|----------|---------------|
| 11 | What analytics platforms do you already use? (Athena/Snowflake/Databricks/Redshift) | Determines primary engine |
| 12 | Is the data regulated? (HIPAA/PCI/SOX/GDPR) | Determines governance requirements |
| 13 | Do you need column-level or row-level access control? | Determines Lake Formation / Snowflake governance |
| 14 | Is cross-account or cross-organization data sharing required? | Determines sharing mechanism |
| 15 | Who approves data access? (data owner, security team, compliance) | Determines approval workflow |

## 4. Technical Constraints

| # | Question | Why it matters |
|---|----------|---------------|
| 16 | Is FSx for ONTAP already deployed? (version, region, deployment type) | Determines if S3 AP is available (requires 9.17.1+) |
| 17 | Is the analytics platform in the same AWS region as FSx? | Same-region required for S3 AP |
| 18 | Are there network restrictions? (VPC isolation, no internet egress) | Determines AP network origin (VPC vs Internet) |
| 19 | What is the FSx provisioned throughput? | Determines concurrent query capacity |
| 20 | Are there existing ETL pipelines copying data to S3? | Quantifies current cost to eliminate |

## 5. PoC Logistics

| # | Question | Why it matters |
|---|----------|---------------|
| 21 | What is the PoC timeline? (1 day / 1 week / 2 weeks) | Scopes deliverables |
| 22 | Who is the technical contact for the PoC? | Coordination |
| 23 | Can we use synthetic/sample data, or must we use real data? | Determines data handling requirements |
| 24 | What does "success" look like for you? | Defines Go/No-Go criteria |
| 25 | What would make you say "No-Go"? | Identifies deal-breakers early |

---

## Engine Selection Guide (based on answers)

| If the customer says... | Recommended engine | Module |
|---|---|---|
| "We just want to query NAS data cheaply" | Athena | 02 |
| "We need AI on our documents (summarize, search)" | Snowflake + Cortex AI | 03 |
| "We already use Databricks for everything" | DataSync → Databricks UC | 04 |
| "We need Spark ETL with write-back" | EMR Serverless | 05 |
| "Budget is the #1 concern" | DuckDB Lambda | 06 |
| "We need enterprise governance (column/row/tag)" | Lake Formation | 07 |
| "We need to share data with partners" | Snowflake Data Sharing or Delta Sharing | 03 or 04 |
