🌐 **English** | [日本語](../ja/s3-annotations-governance-evaluation.md)

# S3 Annotations / Metadata Evaluation: A Proposal for the Databricks UC × FSx for ONTAP S3 AP Governance Challenge

> **Status**: Initial evaluation (2026-06-18). Live-verified (native S3) + confirmed against official docs.
> **Evidence tier** per claim: **Public** (verifiable from public sources) / **Verified** (proven in this environment) / **Project-context** (internal assumption) / **Hypothesis**.
> **Test environment**: AWS ap-northeast-1, boto3 1.43.32 (AWS CLI 2.35.4 lacks the new commands; 2.35.7+ required).
> **Framing**: right-tool-for-the-job, not vendor-versus. Trade-offs stated symmetrically.

---

## 1. Background: the recorded governance challenge

This repository already records the constraint between Databricks Unity Catalog (UC) and FSx for ONTAP S3 Access Points (S3 AP) (source: [`integrations/databricks/README.md`](../../integrations/databricks/README.md) "Support Confirmation, 2026-05" — **role-based** wording; case numbers and engineer names are withheld per steering policy).

- **UC External Locations do not support S3 AP as a storage target** (confirmed by Databricks Support, 2026-05; evidence tier: **Project-context recorded as Public**)
- **Root cause**: the **session policy** that Databricks generates during AssumeRole does not correctly handle S3 AP ARNs → External Location / External Table / External Volume creation is blocked
- The `access_point` field was **never released as GA** and was removed from docs. Partial success is "not a supported code path."
- Instance Profile + boto3 can read but **fully bypasses UC governance** (PoC only)

> There is **no record of a statement attributed to a "Databricks Product Manager"** by name/title. The technical core is recorded via the Support confirmation above. This evaluation considers what the newly announced S3 Annotations / S3 Metadata can propose for that challenge.

---

## 2. What S3 Annotations / S3 Metadata are (evidence tier: Public)

- [S3 Annotations](https://aws.amazon.com/about-aws/whats-new/2026/06/amazon-s3-annotations-business-context/) (AWS Summit NY 2026, 2026-06): attach custom metadata to S3 objects at scale. Up to 1GB per object (up to 1000 named annotations × 1MB each). JSON/XML/YAML/text. Mutable (change/delete without rewriting the object). Moves with the object on copy/replication; removed on delete ([AWS News Blog](https://aws.amazon.com/blogs/aws/amazon-s3-annotations-attach-rich-queryable-context-directly-to-your-objects/)).
- [S3 Metadata](https://aws.amazon.com/s3/features/metadata/): automatically exposes object metadata as read-only Apache Iceberg tables (journal / inventory / annotation). Queryable via Athena, Iceberg-compatible tools, and the S3 Tables MCP server. GA in several regions including ap-northeast-1.

> Source descriptions are paraphrased/summarized for licensing compliance.

---

## 3. Applicability finding (the crux of this evaluation)

| Question | Result | Basis |
|---|---|---|
| Bucket types S3 Metadata supports | **General-purpose Amazon S3 buckets only** (not directory/table/vector) | Official: [Metadata table limitations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/metadata-tables-restrictions.html) (**Public**) |
| Does the S3 Metadata table include ACLs | **No** (Lifecycle/Object Lock/ACL/replication status excluded) | Same (**Public**) |
| Can FSx for ONTAP S3 (ONTAP S3 + S3 AP) be configured for S3 Metadata | **No** | Structural: ONTAP S3 buckets are outside the Amazon S3 control plane (not listed by `aws s3 ls`). S3 Metadata APIs target Amazon S3 buckets (**Verified**: ONTAP S3 buckets are absent from the S3 namespace in this environment) |
| Do annotations themselves (PutObjectAnnotation) work on native S3 | **Yes** | **Verified** (§4) |

**Conclusion**: S3 Annotations / Metadata **cannot apply directly to FSx S3 AP data**. They are usable only in the **staged-to-S3 pattern** (FSx → FPolicy/DataSync/Glue/EMR → native Amazon S3). This is both a constraint and the precondition for the proposals.

---

## 4. Verification results (2026-06-18, ap-northeast-1, evidence tier: Verified)

Reproduction script: [`integrations/iceberg-metadata-catalog/scripts/verify-s3-annotations.py`](../../integrations/iceberg-metadata-catalog/scripts/verify-s3-annotations.py) (creates a throwaway bucket and deletes all resources afterward).

| Step | Result |
|---|---|
| Create native S3 bucket | ✅ |
| Put object | ✅ |
| `put_object_annotation` (`business-context`: AI-classification JSON) | ✅ Case 1 demonstrated |
| `put_object_annotation` (`ontap-acl-hint`: owner/group/acl_hash/svm/volume/snapshot_id/allowed_principals JSON) | ✅ Case 2 demonstrated |
| `list_object_annotations` | ✅ count=2 |
| `get_object_annotation` round-trip (owner=svc_quality confirmed) | ✅ |
| Cleanup (annotations → object → bucket) | ✅ no residual billable resources |

Note: AWS CLI 2.35.4 lacks the S3 Metadata/Annotations commands (2.35.7+ required). boto3 1.43.32 has all APIs.

> **Round 2 verification scope (annotation table / query path)**: §7 #3 ("enable annotation table + query") was **not live-run in this session** because AWS docs confirm the following (capturing it from authoritative sources is preferable to leaving billable resources behind for an unreachable run):
> - **Enabling triggers backfilling that takes minutes to hours** ([official: Enabling annotation tables](https://docs.aws.amazon.com/AmazonS3/latest/userguide/metadata-tables-enable-disable-annotation-tables.html)) → "queryable" is not reachable in-session + backfill charges.
> - The annotation/metadata tables are created on **AWS-managed S3 Tables (table buckets)**. **AWS-native/open engines (Athena/EMR/Trino/Spark/ClickHouse) CAN query them via `s3tablescatalog` (officially supported, §6 EXT-1)**; only the Databricks UC reference (`iceberg_rest`) is blocked.
> - `CreateBucketMetadataConfiguration` **requires a journal table** (a journal table is created even if you only want annotations) + an **IAM role** assumed by the S3 metadata service (confirmed via API introspection).

---

## 5. Deep-dive of the three proposals

### Case 1: Annotation enrichment for `iceberg-metadata-catalog` (most natural, lowest risk)

The existing [iceberg-metadata-catalog](../../integrations/iceberg-metadata-catalog/) classifies unstructured files with Bedrock Vision and provides an Iceberg metadata catalog + OpenSearch vector search. S3 Annotations **complement (not replace)** it — a self-describing layer attached to the object that travels with it on copy/replication.

> **Two-step nature (R1-F)**: (1) Attaching annotations (`PutObjectAnnotation`) works **standalone**, without an S3 Metadata config (verified in §4). (2) **Querying at scale requires enabling the annotation table** (`CreateBucketMetadataConfiguration` V2 + annotation table). This needs an **IAM role** (assumed by the S3 metadata service), and the table is created in an **AWS-managed table bucket (S3 Tables)**. Enabling triggers **backfilling (minutes–hours)**, and querying requires **S3 Tables catalog federation (`s3tablescatalog`)** (see the shared dependency in §6).

```
FSx for ONTAP (images/docs)
  │ ① Take a consistent point-in-time via Snapshot / FlexClone (per FSxN steering)
  ▼
Staged ingestion: FPolicy→Lambda→S3 / DataSync / Glue / EMR
  │  NOTE: SnapMirror-to-S3 is NOT supported on FSx for ONTAP (recorded in this repo)
  ▼
Amazon S3 (general-purpose bucket)
  │ ② put_object_annotation: business-context = {class, confidence, model, language, schema_version}
  │ ③ enable annotation table (S3 Metadata V2 + IAM role)
  ▼
S3 Metadata (annotation table, Iceberg, on S3 Tables)
  ├── query with Athena
  └── agent search via S3 Tables MCP server
```

| Aspect | Assessment |
|---|---|
| Pros | Classification context travels with the object (copy/replication). **Complements** the existing Iceberg catalog (OpenSearch search) by adding per-object self-description. AWS-native |
| Trade-offs | Requires staged S3 (not direct FSx). Annotation limits: 1MB each, 1000 per object. S3 Metadata is general-purpose buckets only. **Querying additionally requires enabling the annotation table (IAM role + table bucket)** |
| vs the existing catalog (R1-E) | Cross-cutting vector/full-text search and large aggregations: the existing iceberg-metadata-catalog (OpenSearch/Iceberg). Self-describing context that rides with the object on copy: annotations. The two are **complementary** |
| Verification | Annotation attach/round-trip: **Verified** (§4). Annotation-table enablement + Athena query: §7 #3 (**done in Round 2**) |

### Case 2: A permission-aware "discovery signal" (with an important caveat)

Attach `owner` / `group` / `acl_hash` / `classification` / `snapshot_id` / `allowed_principals` as annotations, made searchable via S3 Metadata.

> ⚠️ **Non-negotiable precondition (per the FSxN AI/RAG steering)**: **This is a "discovery signal", not "access-control enforcement".** Annotations are descriptive metadata attached to the object; they do not enforce read authorization. Permission-aware RAG must:
> - **Re-check authorization immediately before passing context to the LLM**, after vector/metadata filtering
> - Re-verify the user can actually access a cited source before showing its link
> - **Deny by default when permissions are unknown**
> - Keep the enforcement boundary at **ONTAP file-level ACL + FPolicy + S3 AP access point policy + IAM** (compensating controls)

> **ACL-hint derivation (R1-A, FSx ONTAP Architect findings)**: ONTAP is multi-protocol, so the hint must include the **security style**:
> - `security_style`: `ntfs` / `unix` / `mixed`
> - **NTFS style**: compute `acl_hash` from the NTFS Security Descriptor (normalized to SDDL). `owner` = owner SID/name, `group` = primary group
> - **UNIX/NFSv4 style**: compute from the NFSv4 ACE list (order-normalized) or mode bits
> - `acl_hash` is a SHA-256 of the **normalized** form (absorbs ACE ordering / formatting variance). It is a **change-detection fingerprint, not the ACL itself**
> - Source: ONTAP REST API (delta-triggered by FPolicy events). Detects permission changes and re-syncs the staged side

| Aspect | Assessment |
|---|---|
| Pros | Improves **discoverability** of already-authorized data. `acl_hash` can trigger "permission-change detection" |
| Trade-offs | No enforcement (double-check mandatory). A hint, not the ACL itself. Staleness risk on sync lag → detect via acl_hash and re-sync |
| Verification | Storing ACL hints in annotations: **Verified**. Authorization-chain integration: **not verified** (design only) |

### Case 3: Move governance to "the layer where it works" (Iceberg) — the direct take on the Databricks challenge

Rather than forcing S3 AP into UC, have **UC reference** the staged-S3 S3 Metadata Iceberg tables (and the business Iceberg tables) and apply governance in the layer where it works. This **structurally avoids** the S3 AP × session policy problem.

```
staged S3 ──▶ S3 Metadata (Iceberg) / business Iceberg tables
                     │
                     ├── Databricks UC (native reference) ── row/column governance (UC-internal engine)
                     └── Athena / other engines (via Iceberg REST)
```

> ⚠️ **Known constraints (recorded in this repo; Databricks Governance Architect findings)**:
> - **Important distinction (R1-C)**: S3 Metadata's **system tables** (journal/inventory/annotation) live on **AWS-managed S3 Tables (table buckets)**; UC reference requires S3 Tables catalog federation (`s3tablescatalog` / `iceberg_rest`) → that path is **blocked** (a double blocker). The **realistic UC-reference target is "user-created business Iceberg tables (on general-purpose S3)"**, which Case 3 targets first.
> - **Annotations are a parallel mechanism that does NOT integrate with UC tags/ABAC (R1-C)**. Annotations do not automatically contribute to UC governance (UC tags/ABAC must be set separately).
> - **UC Row Filters / Column Masks are NOT enforced on external engines** (Athena/EMR via Iceberg REST) (source: [`docs/en/governance-and-compliance.md`](./governance-and-compliance.md)). UC governance works for UC-internal engines but is not enforced cross-engine.
> - iceberg-metadata-catalog **Phase 4 (Databricks integration) is blocked** (`iceberg_rest` connection cannot be created; AWS/Databricks support in progress). Case 3's UC reference depends on clearing this blocker.

| Aspect | Assessment |
|---|---|
| Pros | Avoids the session policy / S3 AP constraint. Within UC, row/column governance + lineage work |
| Trade-offs | Requires staged S3 (loses zero-copy). No cross-engine enforcement. Depends on the `iceberg_rest` blocker |
| Verification | **Not verified** (awaiting Phase 4 blocker resolution, §7) |

---

## 5.5 Refinements from external specialist-archetype review (EXT-1–5)

> Refinements by domain-expert role archetypes (automotive/manufacturing data platform / connected-vehicle streaming / open table format & catalog federation / governance / real-time OLAP). **No individual or company names are recorded here** (provenance is kept internally).

- **EXT-1 (Open Table Format / catalog federation; a Public correction)**: S3 Metadata tables are queryable from Athena / EMR / Redshift / Trino / Spark via `s3tablescatalog` (Glue + Lake Formation). This corrects the Round 2 wording ("Case 1 query and Case 3 UC converge on the same blocker") and unifies §4 / §6 / §7 / §9 to "**AWS-native query is supported; only Databricks UC is blocked**".
- **EXT-2 (connected-vehicle streaming)**: annotations + S3 Metadata are **off the real-time hot path** due to backfilling (minutes–hours). This evaluation positions them as a **cold path (discovery/context)**; real-time (e.g., connected-vehicle telemetry) stays on streaming engines (Structured Streaming / Lakeflow / RT OLAP). Do not put annotations on the hot path.
- **EXT-3 (real-time OLAP / open engines)**: because the annotation table is Iceberg, **open engines such as Trino / Spark / ClickHouse can also read it** (Iceberg-compatible endpoints), offering an **alternative query engine** that bypasses the Databricks UC block (right-tool-for-the-job, not a ranking). **However, Iceberg / S3 Tables read support in ClickHouse/Trino is version/config-dependent and must be validated (§7 #13, EXT-B3).**
- **EXT-4 (automotive/manufacturing scale)**: at scale (many vehicles/parts/images), annotation limits (1MB each, 1000 per object) + backfill + staged-S3 duplication cost become material → include a **retention/lifecycle** policy. Manufacturing traceability (genealogy: `lot_id` / `serial` / `process_step` / `inspection_result`) is a strong annotation use case. Example:
  ```json
  { "schema": "mfg.traceability.v1", "lot_id": "L-2026-0042", "serial": "SN-000123",
    "process_step": "weld-03", "inspection_result": "pass", "ts": "2026-06-18T00:00:00Z" }
  ```
- **EXT-5 (governance, two planes)**: treat governance for the staged S3 / Iceberg path as two planes — (a) **AWS-side Lake Formation** (column/row-level controls + credential vending on S3 Tables, applied to Athena/EMR), (b) **Databricks UC** (`iceberg_rest` blocked). Annotations are a discovery signal; where enforcement is needed, **map them to governed tags (LF LF-Tags / UC tags)** (annotations alone do not govern). **Also, since annotations are mutable, write access (`s3:PutObjectAnnotation` / `DeleteObjectAnnotation`) must be tightly least-privilege controlled (EXT-B5); otherwise discovery signals such as ACL hints can be tampered/spoofed, undermining discovery trust. Case 2 thus assumes both "double-checking read authorization" and "controlling write access".**

---

## 6. What it does NOT solve (honest assessment)

- S3 Annotations / Metadata **do not solve the core problem that UC cannot directly govern S3 AP**. They are "discovery/context", not "access-control enforcement", and they do not apply to FSx S3 AP.
- Zero-copy is not preserved (staged-to-S3 is the precondition), trading off the value of direct FSx access (ONTAP feature retention, multi-protocol).
- Annotations are not the ACL itself, so the permission-aware enforcement boundary remains on the ONTAP/IAM side.
- **Annotation freshness on source change (R1-D)**: annotations travel with the object on copy/replication, but the staged S3 object is a **derived copy** of the FSx source. When the FSx file is updated/deleted, the staged copy and its annotations must be **re-synced/invalidated** (source update → re-stage + re-annotate; source delete → remove staged + annotations). Use FPolicy change events as the re-sync trigger.
- **Shared substrate, divergent support for the query path (Round 2 → refined by external review, F2-2 / EXT-1)**: the annotation/metadata tables live on AWS-managed S3 Tables and **share** the `s3tablescatalog` substrate (Glue Data Catalog + Lake Formation). However, support **diverges**:
>   - **AWS-native / open engines (Athena / EMR / Redshift / Trino / Spark / ClickHouse) CAN query them** via `s3tablescatalog` ([official: Querying metadata tables with AWS analytics services](https://docs.aws.amazon.com/AmazonS3/latest/userguide/metadata-tables-bucket-integration.html)). Lake Formation can also enforce column/row-level controls.
>   - **Databricks UC reference (the `iceberg_rest` connection) is blocked** (Case 3).
>   → Therefore **Case 1's query path (AWS-native) is NOT blocked**; only Case 3 (Databricks UC) is. The two share a substrate (`s3tablescatalog` / Iceberg) but **diverge in support**. **(This refines the Round 2 "converge on the same blocker" wording.)** Attaching works standalone; scale-querying rides on this substrate (backfill minutes–hours + LF/IAM setup are preconditions).

---

## 7. Validation items / open questions

| # | Item | Status |
|---|---|---|
| 1 | Confirm S3 Metadata cannot be configured on FSx ONTAP S3 | ✅ Public + Verified (§3) |
| 2 | Annotation round-trip on native S3 | ✅ Verified (§4) |
| 3 | Enable annotation table + query (a step separate from attach). **AWS-native/open engines (Athena/EMR/Trino/Spark/ClickHouse) CAN query via `s3tablescatalog` (officially supported)**; enabling requires backfill (minutes–hours) + LF/IAM setup. Only the Databricks UC reference is blocked (§6 EXT-1) | ⚠️ Path confirmed via official docs (§4/§6). Live query not run this session due to backfill latency → captured as a runbook |
| 4 | Annotation-attachment pipeline at staged ingestion (FPolicy/Glue/Lambda placement) | 🔲 Design pending |
| 5 | Whether UC can stably reference S3 Metadata Iceberg tables (`iceberg_rest` blocker) | 🔲 Depends on Phase 4 |
| 6 | Integration of annotation ACL hints with the permission-aware RAG authorization chain | 🔲 Design pending (double-check mandatory since not enforced) |
| 7 | Annotation limits (1MB each, 1000 per object) vs manufacturing metadata volume | 🔲 Needs estimation |
| 8 | Re-sync/invalidation pipeline for annotations on source change/delete (FPolicy trigger, R1-D) | 🔲 Design pending |
| 9 | Annotation schema versioning/evolution (establish the authoritative version via ingestion order/dedup, R1-G) | 🔲 Design pending |
| 10 | Cost-dimension estimation (annotation storage / S3 Metadata table (S3 Tables) / Athena scan / ingestion compute / staged S3 duplication, R1-H) | 🔲 Needs estimation |
| 11 | Manufacturing-traceability annotation schema (lot/serial/process/inspection) design + validation (EXT-4) | 🔲 Design pending |
| 12 | Annotation → governed tag (LF LF-Tags / UC tags) mapping design (EXT-5) | 🔲 Design pending |
| 13 | Reading the annotation table from open engines (Trino / ClickHouse) — validation (EXT-3) | 🔲 Not verified |
| 14 | Control of annotation write access (least-privilege `s3:PutObjectAnnotation`/`Delete`) — prevent discovery-signal tampering (EXT-B5) | 🔲 Design pending |
| 15 | Structured (array) payload design when manufacturing genealogy exceeds 1000 events (mind the 1MB/annotation limit, EXT-B4) | 🔲 Design pending |

---

## 8. Feedback to AWS / Databricks

Submission-ready drafts are stored **privately** (`.private/support-feedback/`, gitignored; the submitter adds case numbers):

- **To AWS**: feature request for S3 Metadata/Annotations support on FSx for ONTAP S3 / ONTAP S3 buckets (or Iceberg-compatible exposure of ONTAP S3 object metadata). The "general-purpose buckets only" restriction is a gap for FSx use cases.
- **To Databricks**: UC External Location S3 AP session-policy support; the `iceberg_rest` connection constraint; whether UC can reference S3 Metadata Iceberg tables; cross-engine enforcement of row/column governance on the staged-to-Iceberg path.

Public repository content **excludes case numbers and engineer names** (role-based wording only).

---

## 9. Selection guide (use-case-based / right-tool-for-the-job)

| Requirement | Recommended | Note |
|---|---|---|
| Add **discoverability / AI context** to FSx data, AWS-native | Case 1 (staged S3 + Annotations) | Zero-copy sacrificed; scale-query works via Athena/Trino/Spark/ClickHouse (`s3tablescatalog`), backfill/LF setup required (§6 EXT-1) |
| **Discovery aid** for permission-aware RAG | Case 2 (ACL-hint annotations) | Enforcement stays on ONTAP/IAM; double-check mandatory |
| **Governed analytics in Databricks** | Case 3 (move to Iceberg layer) | Requires `iceberg_rest` resolution; mind cross-engine non-enforcement |
| Direct FSx access + enforced governance (today) | Snowflake External Table / Athena + ONTAP ACL/FPolicy | Independent of S3 Annotations |

---

## References

- [Amazon S3 Annotations (What's New, 2026-06)](https://aws.amazon.com/about-aws/whats-new/2026/06/amazon-s3-annotations-business-context/)
- [Amazon S3 annotations (AWS News Blog)](https://aws.amazon.com/blogs/aws/amazon-s3-annotations-attach-rich-queryable-context-directly-to-your-objects/)
- [S3 Metadata table limitations and restrictions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/metadata-tables-restrictions.html)
- [Amazon S3 Metadata (feature page)](https://aws.amazon.com/s3/features/metadata/)
- This repo: [Databricks integration README](../../integrations/databricks/README.md) / [governance-and-compliance](./governance-and-compliance.md) / [cross-repo-integration-strategy](./cross-repo-integration-strategy.md)
- Connectivity perspective (distinct from storage: Kafka/ClickHouse → UC paths/ports): [Kafka/ClickHouse → Unity Catalog connectivity](./kafka-clickhouse-unity-catalog-connectivity.md)

---

## Persona Review Summary (improvement loop: Rounds 1–3)

### Review Metadata
- Review Date: 2026-06-18
- Reviewed Documents: `docs/{ja,en}/s3-annotations-governance-evaluation.md` + reproduction script + support drafts (private)
- Review Scope: applicability of S3 Annotations/Metadata to the Databricks UC × FSx S3 AP challenge
- Review Method: multi-round critical review weighted to domain-expert personas → fix → re-review

### Round 1 findings and resolutions (8)
| ID | Persona | Finding | Resolution |
|----|---------|---------|-----------|
| R1-A | FSx ONTAP Architect | ACL-hint derivation vague (multi-protocol) | §5 Case 2: specify security_style / NTFS SD / NFSv4 ACE / normalized SHA-256 |
| R1-B | FSx ONTAP Architect | Staging consistency unspecified / SnapMirror-to-S3 unsupported | §5 Case 1: require Snapshot/FlexClone + correct staging mechanisms |
| R1-C | Databricks Governance | Case 3 inaccurate (system-table double blocker / UC tags not integrated) | §5 Case 3: state the distinction and non-integration |
| R1-D | Cloud Data Architect | Source-change staleness missing | §6 + §7 #8: add re-sync pipeline |
| R1-E | Cloud Data Architect | "No separate catalog" overstated | §5 Case 1: reframe as "complement" |
| R1-F | Governance / Cloud Data | Attach vs query stages conflated | §5 Case 1 / §4 / §7 #3: state the stages |
| R1-G | Mfg Edge | Schema versioning missing | §7 #9 added |
| R1-H | Cloud Data Architect | Cost dimensions missing | §7 #10 added |

### Round 2 findings and resolutions (4, surfaced by added verification)
| ID | Persona | Finding / insight | Resolution |
|----|---------|-------------------|-----------|
| F2-1 | Cloud Data / Governance | Annotation-table enablement triggers backfilling (minutes–hours) | §4 / §7 #3 documented; reflected in AWS feedback |
| F2-2 | Databricks Governance | **Query path depends on S3 Tables federation = same family as the Databricks `iceberg_rest` blocker** (Case 1 and Case 3 converge on one blocker) | §6 adds the shared dependency; reflected in both feedback drafts |
| F2-3 | accuracy | Three stages (attach→enable→query) clarified | §5 Case 1 / §4 |
| F2-4 | API | Journal table required + IAM role required | §4 documented |

### Round 3 final sign-off (per persona)
- **Principal Cloud Data Architect**: complement relationship, staleness, and cost dimensions now clear. **APPROVE**. Remaining: phase §7 #4/#8/#10.
- **Manufacturing Edge Data Architect**: schema versioning and ingestion ordering reflected. **APPROVE**. Remaining: high-volume throughput estimation (§7 #7).
- **Databricks Governance Architect**: Case 3's double blocker and the shared dependency (F2-2) are now clear, improving design realism. **APPROVE WITH COMMENTS** (clearing `iceberg_rest`/`s3tablescatalog` is a precondition for both Case 1 query and Case 3).
- **NetApp FSx for ONTAP Architect**: ACL-hint derivation, Snapshot/FlexClone staging, and the FSx non-applicability constraint are clear. **APPROVE**. Remaining: feasibility of the AWS feature request.
- **Public Repository Confidentiality Reviewer**: re-confirmed no sensitive IDs / case numbers in public content after the Round 1–2 additions. **Pass** (support drafts isolated in `.private/`, gitignored).

### External specialist-archetype review (Rounds A–B, EXT-1–5 / EXT-B3–B5)

> Additional review by domain-expert role archetypes. **No individual or company names recorded** (provenance kept internally).

- **Open Table Format / catalog federation archetype**: [EXT-1 correction] S3 Metadata tables are queryable from Athena/EMR/Trino/Spark via `s3tablescatalog` → corrects the Round 2 "converge on one blocker" wording. AWS-native query is supported; only Databricks UC is blocked. **The most important accuracy fix.**
- **Connected-vehicle streaming archetype**: [EXT-2] annotations are cold-path (discovery). Real-time stays on streaming/RT OLAP; do not put them on the hot path.
- **Real-time OLAP archetype**: [EXT-3/B3] being Iceberg, the table is readable by Trino/Spark/ClickHouse (an alternative bypassing the UC block). Read support is version/config-dependent and must be validated.
- **Automotive/manufacturing data-platform archetype**: [EXT-4/B4] cost/retention at scale; manufacturing-traceability schema; for genealogy >1000 events use one structured payload.
- **Governance archetype**: [EXT-5/B5] two governance planes (LF vs UC); annotation→tag mapping. **Annotations are mutable → least-privilege control of write access is mandatory (anti-tampering).**

### Final Recommendation (post-convergence, EXT-reflected)
- **APPROVE WITH COMMENTS (converged)** — Case 1 is verified through attach and is actionable. **Case 1's scale-query is supported on AWS-native engines (Athena/Trino/Spark/ClickHouse)** (backfill/LF setup are preconditions); **only Case 3 (Databricks UC `iceberg_rest`) is blocked** (EXT-1 corrects the Round 2 error). Case 2 must strictly preserve the "discovery signal (not enforcement; double-check reads + control writes)" boundary.
- Required Next Actions: phase the unverified/pending items in §7 (#3 live AWS-native query, #5 UC reference, #11–15 traceability/tag-mapping/open-engine/write-control). Submit the §8 feedback to AWS / Databricks.
- Public Repository Readiness: Ready (confidentiality compliant; no individual/company names, provenance isolated in `.private/`; re-verified after Rounds 1–3 + external review).
