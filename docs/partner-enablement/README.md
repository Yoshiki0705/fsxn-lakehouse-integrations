# SI Partner Enablement: FSx for ONTAP AI Metadata Catalog

> Everything SI partners need to propose, build, and operate the FSx for ONTAP AI Metadata Catalog for their customers.

---

## What's Included

| Asset | Description | Location |
|-------|-------------|----------|
| CloudFormation Templates | One-click infrastructure deployment | `integrations/iceberg-metadata-catalog/cloudformation/` |
| Demo Scripts | Automated end-to-end demo execution | `integrations/iceberg-metadata-catalog/demo/scripts/` |
| 20 Industry Templates | Pre-built AI classification configs | `integrations/iceberg-metadata-catalog/use-cases/` |
| Infra Request Template | Customer environment sizing worksheet | `docs/partner-enablement/infra-request-template.md` |
| Sample Data Generator | Generate realistic test files per industry | `integrations/iceberg-metadata-catalog/demo/sample-data/` |
| ROI Calculator | Cost/benefit analysis for customer proposals | `docs/sales-enablement/roi-calculator.md` |
| Customer FAQ | Common questions with bilingual answers | `docs/sales-enablement/customer-faq.md` |

---

## Implementation Timeline

### Phase 1: Infrastructure (1–2 days)

- Deploy FSx for ONTAP (or validate existing environment)
- Configure S3 Access Point
- Deploy S3 Tables (Iceberg) namespace
- Set up Lambda functions and IAM roles
- Validate network connectivity (VPC, security groups)

### Phase 2: AI Pipeline (2–3 days)

- Configure FPolicy on FSx for ONTAP
- Deploy Bedrock-powered classification pipeline
- Configure industry-specific classification templates
- Set up OpenSearch Serverless collection
- Run initial batch processing on existing files
- Validate AI classification accuracy with customer

### Phase 3: BI/Search Interface (1–2 days)

- Configure Athena workgroup and saved queries
- Deploy OpenSearch Dashboards (search UI)
- Set up Lake Formation governance policies
- Create customer-specific dashboards
- Conduct user acceptance testing

**Total: 5–7 business days** from kickoff to production

---

## SI Revenue Model

### Initial Build Revenue

| Component | Typical Effort | Notes |
|-----------|---------------|-------|
| Infrastructure setup | 2 days | CloudFormation + networking |
| AI pipeline configuration | 3 days | Template customization + accuracy tuning |
| BI/Search UI | 2 days | Dashboards + saved queries |
| Training & handover | 1 day | Admin training + documentation |
| **Total** | **8 days** | Billable as fixed-price or T&M |

### Monthly Operations Revenue

| Service | Description | Cadence |
|---------|-------------|---------|
| FPolicy monitoring | Alert on pipeline failures, throughput anomalies | Daily |
| Bedrock tuning | Improve classification accuracy based on feedback | Monthly |
| Dashboard maintenance | New queries, views, and reports | As needed |
| Template updates | Add new file categories as business evolves | Quarterly |
| Cost optimization | Review Lambda/Bedrock usage, right-size | Monthly |

### Expansion Opportunities

- Additional departments/file shares
- Additional industry templates
- Multi-region DR configuration
- Snowflake/Databricks integration (when available)
- Custom AI model training (fine-tuning)

---

## PoC Execution Checklist

### Pre-PoC (Day 0)

- [ ] Customer signs off on PoC scope and success criteria
- [ ] AWS Account ID and region confirmed
- [ ] FSx for ONTAP environment available (or provisioned)
- [ ] Sample files identified (100–1000 representative files)
- [ ] Network connectivity validated (VPC peering/endpoints)
- [ ] Bedrock model access enabled in target region

### Phase 1: Deploy (Day 1–2)

- [ ] CloudFormation stack deployed successfully
- [ ] S3 Access Point validated (can read files from FSx)
- [ ] Lambda functions tested with sample file
- [ ] S3 Tables namespace created and accessible from Athena

### Phase 2: Pipeline (Day 3–5)

- [ ] FPolicy configured and events flowing
- [ ] AI classification running on sample files
- [ ] Classification accuracy reviewed with customer (>85% target)
- [ ] OpenSearch index populated
- [ ] Vector embeddings generated

### Phase 3: Validation (Day 6–10)

- [ ] Customer can search files via Athena SQL
- [ ] Customer can search files via OpenSearch UI
- [ ] PII detection validated (if applicable)
- [ ] Performance validated (42s target for single file)
- [ ] Cost projection presented to customer
- [ ] Go/No-Go decision documented

### Post-PoC

- [ ] PoC results summarized in customer-facing report
- [ ] Production proposal with timeline and pricing
- [ ] Ongoing ops agreement drafted

---

## Key Links

| Resource | Link |
|----------|------|
| Solution Overview (JA) | [`docs/sales-enablement/solution-overview-ja.md`](../sales-enablement/solution-overview-ja.md) |
| Customer FAQ | [`docs/sales-enablement/customer-faq.md`](../sales-enablement/customer-faq.md) |
| ROI Calculator | [`docs/sales-enablement/roi-calculator.md`](../sales-enablement/roi-calculator.md) |
| Architecture Comparison | [`docs/sales-enablement/architecture-comparison.md`](../sales-enablement/architecture-comparison.md) |
| Quick Win Demo (30 min) | [`integrations/iceberg-metadata-catalog/demo/scenarios/quick-win-30min.md`](../../integrations/iceberg-metadata-catalog/demo/scenarios/quick-win-30min.md) |
| Manufacturing Demo (JA) | [`integrations/iceberg-metadata-catalog/demo/scenarios/industry-manufacturing-ja.md`](../../integrations/iceberg-metadata-catalog/demo/scenarios/industry-manufacturing-ja.md) |
| GitHub Repository | [fsxn-lakehouse-integrations](https://github.com/Yoshiki0705/fsxn-lakehouse-integrations) |

---

## Support

For partner enablement questions, demo scheduling, or technical deep-dives, contact Yoshiki Fujiwara.
