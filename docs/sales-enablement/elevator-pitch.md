# 3-Minute Elevator Pitch: FSx for ONTAP AI Metadata Catalog

> Scenario-based scripts (3 minutes each)

---

## Scenario 1: Field Engineer → Customer

### Opening Hook (30 seconds)

"How many terabytes of data are on your file servers right now? Most customers tell us they can't find what they need — or even know what's there. There's a way to make all that data searchable with AI, without moving a single file."

### Problem Statement (45 seconds)

"Unstructured data on file servers has always been invisible to analytics. The traditional approach — copy everything to S3 — doubles your storage cost and creates ongoing sync complexity. Manual tagging? That doesn't scale when thousands of files change daily."

### Solution (60 seconds)

"This solution uses FSx for ONTAP's S3 Access Point to connect an AI pipeline directly to your NAS — no data copy required.

Here's how it works:
1. FPolicy detects when files are created or modified
2. Lambda accesses the file via S3 Access Point (read-only, zero-copy storage)
3. Amazon Bedrock classifies the file and extracts metadata
4. Results go into Apache Iceberg tables, instantly queryable via Athena or OpenSearch

**Files stay on FSx. Only metadata moves.**

Important to note: S3 AP is used read-only in this pipeline (writes are supported) (no write-back from analytics), and AI classification accuracy varies by file type and language. We recommend a PoC to validate on your actual data."

### Evidence (30 seconds)

"In our PoC: file placement to searchable metadata in **42 seconds**. Cost: **$0.07 per file** (for typical 100KB–1MB documents). Monthly operation for 100K files: **$114**. Conservative ROI estimate: payback within 2 weeks.

These are PoC results — production performance depends on your file mix."

### Closing (15 seconds)

"We have a 30-minute hands-on demo. CloudFormation deploys the full stack. Would it be useful to see this running with your kind of files?"

---

## Scenario 2: Field Engineer → SI Partner

### Opening Hook (30 seconds)

"Do any of your customers struggle with finding and managing files on their NAS? We've built a solution package that your team can propose and implement — with CloudFormation templates, demo scripts, and 20 industry templates ready to go."

### Opportunity (45 seconds)

"Many enterprises want to get value from their NAS data but can't justify a full data lake migration. This solution gives them immediate AI-powered search without moving data — and gives you:
- **Initial build engagement** (1–2 week PoC → production deployment)
- **Monthly operations revenue** (pipeline monitoring, accuracy tuning, dashboard maintenance)
- **Repeatable across accounts** (20 industry templates for rapid deployment to other customers)"

### Solution Overview (60 seconds)

"Technically, infrastructure deployment is automated via CloudFormation:

- Phase 1: Infrastructure (1–2 days) — FSx for ONTAP + S3 Tables + Lambda
- Phase 2: AI Pipeline (2–3 days) — Bedrock integration + FPolicy configuration
- Phase 3: Search UI (1–2 days) — Athena + OpenSearch dashboards

Total: **5–7 business days** to production.

Key constraints to share with customers: S3 AP is used read-only in this pipeline (writes supported), FPolicy adds ~1–5ms latency, and Bedrock accuracy should be validated in a PoC. These are straightforward conversations."

### Evidence (30 seconds)

"Numbers: pipeline runs in 42 seconds, $0.07/file. Conservative ROI for a 50-user department saving 10 minutes/day on search: ~¥300,000/month in productivity — against $114/month in costs."

### Closing (15 seconds)

"We can run a 30-minute hands-on session for your SE team. They can demo it to customers the next day. Let's schedule it."

---

## Scenario 3: Field Engineer → Distributor SE

### Opening Hook (30 seconds)

"For your SEs calling on FSx for ONTAP customers — here's a differentiation story for upselling data analytics on top of existing file storage."

### Market Opportunity (45 seconds)

"Most FSx for ONTAP customers are stuck at 'file server migration done.' The next step is data utilization — and that connects to AWS analytics revenue beyond storage.

Market context:
- Unstructured data growing 60%+ annually
- 80%+ is dark data (unused, unsearchable)
- AI-powered data classification demand is accelerating"

### Solution (60 seconds)

"The pitch to customers is simple:

'Make your FSx for ONTAP files searchable by AI — without copying them anywhere.'

Technical foundation:
- S3 Access Point for zero-copy storage access (read-only)
- Amazon Bedrock for AI classification (Japanese language supported)
- Apache Iceberg (S3 Tables) for metadata management
- Athena/OpenSearch for search and analytics

**Customer needs only their existing FSx for ONTAP environment.**

Be upfront about constraints: read-only access, FPolicy latency (~1–5ms), and classification accuracy needs PoC validation."

### Evidence (30 seconds)

"Demo: 42 seconds end-to-end. Cost: $0.07/file, $114/month for 100K files. Conservative benefit: 10 minutes/day search time saved per user. For 50 users, that's ~$2,500/month in conservative productivity value."

### Closing (15 seconds)

"30-minute SE workshop available. Live demo included — ready for partner introductions the next day."

---

## Common Reference Data

| Item | Value | Caveat |
|------|-------|--------|
| Pipeline time | 42 seconds | Single file; batch depends on concurrency |
| Cost per file | $0.07 | Assumes 100KB–1MB documents |
| Monthly cost (100K files) | $114 | 1,000 changes/day |
| Idle cost | ~$5/month | Minimum OpenSearch + S3 Tables |
| Classification confidence | 0.94 (PoC) | Production varies by file type/language |
| Industry templates | 20 | Pre-configured categories + queries |
| PoC duration | 1–2 weeks | Full validation with customer files |
| Quick demo | 30 minutes | CloudFormation + sample data |

---

*Pair document: [elevator-pitch-ja.md](./elevator-pitch-ja.md)*
