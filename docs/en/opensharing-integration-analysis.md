🌐 **English** | [日本語](../ja/opensharing-integration-analysis.md)

# OpenSharing × FSx for ONTAP: Integration Analysis

> **Status**: Forward-looking architecture analysis. Based on public announcements (2026-06-10). No vendor implementation has been independently validated by this repository yet. Validation tasks are tracked as a future activity.

> **Review note**: This analysis was produced through a multi-lens architecture review. Reviewer lenses are described by **role only** (no individual or employer attribution). Each claim is tagged by evidence tier: **Public** (verifiable from public sources), **Archetype** (generic role-based reasoning).

## What Changed (Public Evidence)

On 2026-06-10, Databricks announced **OpenSharing** — the evolution of the Delta Sharing protocol, now hosted by the Linux Foundation — and a **Storage Ecosystem** of partners that connect on-premises and hybrid storage to Databricks without data movement.

| Fact | Source |
|------|--------|
| OpenSharing is the first open protocol covering AI assets (agent skills, AI models, unstructured data) in addition to structured data | [Databricks Press Release](https://www.databricks.com/company/newsroom/press-releases/databricks-announces-opensharing) |
| Adds support for Apache Iceberg IRC clients, extending reach beyond Delta Sharing recipients | Same |
| Storage Ecosystem connects hybrid/on-prem storage via OpenSharing using a zero-copy architecture into Unity Catalog | [Databricks Blog](https://www.databricks.com/blog/announcing-databricks-storage-ecosystem-governing-enterprise-data-estate-wherever-it-lives) |
| GA / preview launch partners include object-storage and hybrid-storage vendors; additional enterprise storage partners are listed as "coming soon" by end of year | Same |
| Volumes APIs for unstructured data are explicitly previewed as the next step | Same |
| Partner Well-Architected Framework documents the integration blueprint, including two paths to serve Iceberg via the protocol (Delta Shallow Clone or Apache XTable metadata translation) | [Partner Framework](https://databrickslabs.github.io/partner-architecture/data-collaboration/software-defined-storage) |

> FSx for ONTAP is an AWS-managed enterprise storage service with multiprotocol access (NFS/SMB/iSCSI/S3) and data protection features (Snapshot, FlexClone, SnapMirror, FabricPool). The analysis below evaluates how the OpenSharing pattern could complement the existing S3 Access Point integration patterns in this repository.

## Why This Matters for This Repository

The current compatibility matrix lists the Databricks + FSx for ONTAP S3 Access Point path as **blocked** (the platform's session policy does not recognize the S3 AP ARN format). OpenSharing is relevant because its sharing model is based on short-lived presigned URLs, where the sharing server handles only **metadata and access control** while data transfer happens directly between client and storage.

**Architecture-Lens (Archetype) finding**: This separation could allow the S3 AP ARN recognition issue to be bypassed at the architecture level, because the consuming platform interacts with the sharing protocol rather than parsing the storage ARN directly. This is a hypothesis to be validated, not a confirmed result.

## Technical Note: Presigned URL Behavior on FSx for ONTAP

Because the Delta Sharing / OpenSharing model relies on short-lived presigned URLs, the presigned-URL behavior of FSx for ONTAP is central to this analysis. Two questions must be kept separate:

1. **Whether the documentation lists Presign as supported** (the documented stance), and
2. **Whether a client-generated presigned URL actually works** against the endpoint (empirical behavior).

A presigned URL is produced purely by client-side SigV4 query-string signing — no server call is needed to create it. The real question is whether the endpoint honors the signed GET request.

| Endpoint | Documented `Presign` | Observed behavior |
|----------|:--------------------:|-------------------|
| FSx for ONTAP S3 Access Point | Listed as not supported ([AWS docs](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)) | In this repository's prior testing, a client-generated SigV4 presigned URL returned HTTP 200 against the S3 Access Point endpoint |
| ONTAP S3 (native object server) | Supported on ONTAP 9.11+ (SigV4; v2 presign not supported) | Documented capability |

**Takeaway**: "Whether the S3 Access Point documents Presign support" and "whether a client's presigned URL works against it" are different questions. The documented stance alone should not be used to exclude a backend. The native ONTAP S3 object server documents presigned-URL support (SigV4) and is a dependable option; the S3 Access Point path showed working client-generated presigned URLs in prior testing and warrants empirical validation per use case. Use SigV4 (v2 presign is not supported on ONTAP S3).

**Additional path — temporary credentials**: The OpenSharing protocol's credential vending can issue *either* presigned URLs *or* temporary, scoped cloud credentials (e.g. AWS STS), depending on asset type and access mode ([OpenSharing spec](https://github.com/OpenSharing-IO/OpenSharing)). With the temporary-credentials mode, the recipient reads via a standard `GetObject` call rather than a presigned URL. Because `GetObject` is supported on FSx for ONTAP S3 Access Points, this mode sidesteps the presign question entirely and is a strong candidate for the access path.

**Governance granularity note**: Credential vending (presigned URL or temporary credentials) grants access at the storage-location (prefix) level — it does not carry row- or column-level policies. Where fine-grained, cross-engine governance (row filters, column masks) is required, an Iceberg REST catalog with server-side scan planning is the appropriate layer. Treat table-level zero-copy delivery and fine-grained governance as distinct mechanisms, and scope any vended credentials to the specific table location with least privilege.

> This note describes FSx for ONTAP / ONTAP capabilities only. Behavior should be re-validated in your own environment and ONTAP version.

## Scope and Principles

- **Complement, not replacement**: The OpenSharing path complements — it does not replace — the existing AWS-native S3 Access Point patterns (Athena, Glue, EMR, Redshift, SageMaker) already documented in this repository.
- **Source of truth stays on enterprise storage**: The authoritative data remains the Iceberg/Parquet on FSx for ONTAP. Presigned-URL references and any bridged metadata are derived artifacts.
- **Share a curated subset, not everything**: The goal is to expose curated, AI-ready data products, not to share entire volumes indiscriminately. Deny-by-default for data with unknown permissions.
- **Single governance boundary**: Designate one catalog as the governance boundary; avoid distributing policy across multiple catalogs.
- **Interim until native**: Independent validation in this repository uses the open-source Delta Sharing reference implementation (same protocol lineage) ahead of any native vendor implementation.

## Multi-Lens Review

### Principal Cloud Data Architect lens (Archetype)
- **Opportunity**: A presigned-URL sharing model can decouple the consuming platform from storage-specific ARN formats, preserving the zero-copy principle.
- **Concern**: An OpenSharing server becomes a Tier-1 dependency with the same blast radius as a catalog (if it is down, dependent reads stop). Availability, scaling, and P99 latency must be designed.
- **Must validate**: read-only vs read-write; whether Delta or Iceberg is served; whether catalog governance applies to shared tables.

### Manufacturing Edge Data Architect lens (Archetype)
- **Opportunity**: Sensor data, quality-inspection images, and engineering documents on enterprise storage could become directly consumable by ML/AI workloads. The previewed Volumes APIs would extend this to unstructured payloads.
- **Concern**: Edge concerns (time sync, event ordering, deduplication) remain out of scope of the sharing protocol; metadata-to-payload linkage stays a custom design responsibility.

### Lakehouse Governance Architect lens (Archetype)
- **Core change**: Shared data could become subject to centralized governance (lineage, access control, audit) without copying.
- **Trend (Public)**: The Iceberg REST **scan planning** capability (Iceberg 1.11) lets a catalog apply row filters and column masks at plan time, enabling cross-engine attribute-based access control. OpenSharing's Iceberg IRC support may benefit from this. ([Catalog landscape analysis](https://amdatalakehouse.substack.com/p/the-state-of-apache-iceberg-catalogs))
- **Must validate**: write-back support; whether column-level security / row filters / tags travel to shared tables.

### Enterprise Storage Data Services Architect lens (Archetype)
- **Strategic framing**: An OpenSharing endpoint would be a new data-exposure surface alongside NFS/SMB/iSCSI/S3, turning enterprise file storage from a silo into a governed, interoperable node.
- **Differentiators to validate**: point-in-time recovery (Snapshot) as a complement to table time travel; instant logical copies (FlexClone) for shared sandboxes; cross-region replication (SnapMirror) for DR-capable share endpoints; multiprotocol so the same data serves file workloads and AI simultaneously.
- **Open question**: whether a native implementation sits on top of ONTAP S3, S3 Access Points, or an independent data path; and the relative timing of AWS-managed vs on-premises availability.

### Open Catalog Strategist lens (Public)
- As of mid-2026, the open table format question is largely settled in favor of Apache Iceberg; the differentiation has moved to the **catalog layer**, which is becoming the AI control plane. ([Source](https://amdatalakehouse.substack.com/p/the-state-of-apache-iceberg-catalogs))
- **Key distinction**: OpenSharing is a *sharing* protocol; Iceberg REST is a *catalog* protocol. They operate at different layers and are complementary, not mutually exclusive.
- **Unresolved industry problem**: governance policy is not portable across catalogs. The pragmatic answer is to designate a **single catalog as the governance boundary** and route engines through it, rather than running multiple catalogs with inconsistent rules.

### SDS Launch Partner SA lens (Public)
- Public statements from launch-partner storage vendors share a common theme: connect data that **cannot move** (sovereignty, gravity, cost) to cloud AI without migration.
- Implementation pattern: the storage partner stands up an OpenSharing endpoint, connects it to the catalog, and serverless compute queries in place.

## Consensus

1. OpenSharing is a strong candidate path to **bypass the current Databricks blocker** (to be validated).
2. A **multi-surface strategy with Iceberg as the common data plane** — rather than betting on a single sharing protocol — best serves vendor neutrality and cross-engine coexistence.
3. There is value in **validating with an OSS Delta Sharing server backed by FSx for ONTAP first**, ahead of any native vendor implementation.
4. **Governance should be consolidated to a single boundary**; avoid distributing policy across multiple catalogs.
5. The existing unstructured-data metadata catalog work connects strongly to the previewed **Volumes APIs** direction.

## Technical Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D-1 | Two-track parallel PoC: (1) OpenSharing path via OSS Delta Sharing server backed by FSx for ONTAP; (2) Iceberg IRC path via a neutral catalog | Covers both Databricks-optimized and engine-neutral consumption |
| D-2 | Single catalog as governance boundary; evaluate both a platform-native catalog and a neutral catalog for cross-engine ABAC travel | Policy portability across catalogs is unsolved industry-wide |
| D-3 | Publish as a forward-looking analysis and a future blog installment, connected to the unstructured-data catalog work | Maintains series continuity; AWS Community perspective |
| D-4 | Track native vendor implementation; do not wait for it; do not predict GA timing beyond public statements | Evidence discipline |

## Risk Register (Summary)

| Risk | Severity | Mitigation |
|------|----------|------------|
| Sharing server as a new Tier-1 single point of failure | High | HA design, latency monitoring, consider managed options |
| Presigned URL reuse / unauthorized access | High | Short-lived URLs, prefer remote signing, deny-by-default |
| Iceberg/Delta bridging operational complexity | Medium | Metadata-only translation, idempotent design, dead-letter on failure |
| Governance policy fragmented across catalogs | High | Enforce a single governance boundary |
| Permission changes / deletes not reflected in shared metadata | High | Re-sync or event-driven invalidation, deny-by-default |

## Proposed Architecture Pattern

```
Pattern E: OpenSharing (Zero-Copy Governed Access) — analysis stage

FSx for ONTAP → OpenSharing Server (sharing + access control)
                      → Catalog (governance boundary)
                      → Lakehouse Serverless Compute (in-place query)
                      → Iceberg IRC clients (cross-engine)
```

## Open Questions

- Does a native implementation sit on ONTAP S3, S3 Access Points, or an independent path?
- Relative timing of AWS-managed vs on-premises availability?
- Is the sharing server read-only or read-write?
- Do column/row governance policies travel to shared tables?

## Next Activity

A phased validation activity has been defined (read → Iceberg IRC → governance travel → write-back → unstructured design → publication). See the repository's Supported Integrations table and the upcoming blog series for status updates.

---

*This document avoids predicting general-availability dates and distinguishes validated results from forward-looking analysis. Statements attributed to "lenses" are review perspectives by role, not statements by named individuals or companies.*
