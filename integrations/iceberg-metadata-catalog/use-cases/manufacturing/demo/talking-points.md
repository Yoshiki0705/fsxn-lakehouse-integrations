# Manufacturing Demo — Talking Points

## Audience
Quality managers, engineering directors, ISO auditors, plant managers

## Opening (30 sec)
"Your engineering team has thousands of CAD files, QC reports, and maintenance logs on shared storage. Finding the right document takes minutes to hours. What if every file was instantly searchable by content, classification, and part number — in under 2 seconds?"

## Demo Flow (10 min)

| Time | Action | Say |
|------|--------|-----|
| 0:00 | Show file listing (slow) | "This is how you search today — browsing folders, 892ms just to list 40 files" |
| 1:00 | Run metadata scan | "We catalog 40 files in 3 seconds — file type, size, path, all indexed" |
| 2:00 | Show AI classification | "Bedrock Vision classifies this image as 'Invoice' with 95% confidence — no training needed" |
| 4:00 | Athena query by part | "Find all drawings for pump housing P-2000 — 1.8 seconds, regardless of file count" |
| 5:00 | Show time travel | "What did the catalog look like last week? Iceberg time travel gives you instant rollback" |
| 6:00 | PII detection | "7 types of personal information detected automatically — names, emails, phone numbers" |
| 8:00 | Access control | "Revoke access — immediately blocked. Restore — immediately available. Full audit trail." |
| 9:00 | Cost summary | "Total demo cost: $0.07. Monthly at 100K files: $114. S3 copy eliminated: $250 saved." |

## Key Messages

1. **Zero data movement** — Files stay on ONTAP, only metadata is cataloged
2. **2 seconds** — Any file findable via SQL, regardless of volume size
3. **$0.01/file** — AI classification cost (one-time per file)
4. **ISO audit ready** — Full audit trail, time travel, access control
5. **No workflow change** — NFS/SMB access continues unchanged

## Objection Handling

| Objection | Response |
|-----------|----------|
| "We already have a document management system" | "This doesn't replace it — it makes your existing files searchable without migration" |
| "What about security?" | "Read-only access, Lake Formation governance, full CloudTrail audit" |
| "How long to deploy?" | "PoC in 1 day, production in 2 weeks. $100 total PoC cost." |
| "What if AI classification is wrong?" | "Confidence scores let you set thresholds. Low confidence → human review queue." |

## Follow-up
- Share [PoC proposal template](../../../docs/industry-use-cases.md#poc-proposal-template-for-internal-approval)
- Send [infrastructure request](../../../docs/infrastructure-request-template.md) to their platform team
- Schedule 1-week follow-up
