🌐 **English** | [日本語](./databricks-ja.md)

# Feedback: Databricks

Scope: Unity Catalog and Databricks Runtime behaviour with Amazon FSx for NetApp
ONTAP S3 Access Points. Compiled 2026-08-06.

## Summary

This is the integration where the gap has the largest architectural consequence. Not
because reads are impossible — they are achievable — but because the only paths that
work bypass Unity Catalog, and Unity Catalog is the reason to use the platform.

The net effect is that zero-copy analytics and Unity Catalog governance are currently
mutually exclusive for FSx for ONTAP data. Every workaround trades one for the other.

| # | Finding | Status | Consequence |
|:---:|---|---|---|
| 1 | [An Access Point cannot be a Unity Catalog External Location](#1-an-access-point-cannot-be-a-unity-catalog-external-location) | Confirmed by Databricks Support 2026-05-26 | Governance unavailable on the zero-copy path |
| 2 | [`iceberg_rest` is not an accepted Connection Type](#2-iceberg_rest-is-not-an-accepted-connection-type) | `CONNECTION_TYPE_NOT_SUPPORTED`, 2026-05-31 | S3 Tables unreachable as a Foreign Catalog |
| 3 | [Runtime seccomp blocks NFS/SMB mount](#3-runtime-seccomp-blocks-nfssmb-mount) | By design | No direct file system path. Noted as expected, not as a request |

## A note on how these were raised

Both support cases were closed as not entitled, on support-tier grounds rather than
on technical merit. The underlying questions were not evaluated and remain open. They
were moved to the public community forum:

- [Unity Catalog External Location with S3 Access Points](https://community.databricks.com/t5/data-engineering/unity-catalog-external-location-with-amazon-s3-access-points/m-p/160296#M54880) (2026-06)
- [OpenSharing vended STS credentials on S3 Access Points](https://community.databricks.com/t5/data-engineering/opensharing-vended-sts-credentials-on-s3-access-points-verified/m-p/160298#M54881) (2026-06)

This is process feedback rather than product feedback, but it is worth stating: a
platform-capability question that cannot reach an engineer through the support channel
ends up as a forum post competing for attention. If there is a better route for
integration-compatibility questions specifically, that would be useful to know.

---

## 1. An Access Point cannot be a Unity Catalog External Location

**Confirmed by Databricks Support** 2026-05-26. [BLK-001](../en/blocker-tracker.md) ·
[Integration notes](../../integrations/databricks/README.md#support-confirmation-2026-05-26)

`CREATE TABLE` against an Access Point path fails with:

```
UC_CLOUD_STORAGE_ACCESS_FAILURE
```

Support confirmed that an S3 Access Point is not a supported External Location target
and that the `access_point` field is not GA. The recorded root cause is that the
session policy generated during `AssumeRole` does not correctly interpret Access Point
ARNs.

### The partial success is worth describing precisely, because it is misleading

A test on 2026-05-24 listed the bucket root and read explicit file paths successfully.
That looked like partial support. Support characterised it as **"a side effect of
incomplete internal handling, not a supported code path."** Subdirectory listing and
`CREATE TABLE` both failed.

This matters for anyone evaluating: an early test can produce enough success to look
promising, then fail at the point where a table gets defined. Knowing it is not a
supported path saves building on it.

### What works, and what each option costs

| Path | Governance | Copy cost | Trade-off |
|---|:---:|---|---|
| DataSync → standard S3 → External Location | ✅ Full Unity Catalog | ~$27/month/TB | The recommended path. Loses zero-copy, which was the original reason for the architecture |
| Kafka → Structured Streaming → Unity Catalog Delta | ✅ Full | Streaming infrastructure | Fits real-time requirements. Heavier to operate |
| Glue or EMR ETL → standard S3 → Unity Catalog | ✅ Full | Transform + storage | Fits existing batch pipelines |
| Instance Profile + boto3 direct read | ❌ None | Zero | Works, but bypasses Unity Catalog entirely. PoC only — no lineage, tags, masks or row filters |

The last row is the honest summary of the current state: reading FSx for ONTAP data
from Databricks is possible; doing it under governance is not.

### Why this is the gate

Several other blockers only produce value once this one is resolved. If conditional
writes arrive on FSx for ONTAP S3 Access Points, Athena and EMR benefit immediately,
but Databricks Unity Catalog does not — because Unity Catalog cannot address the
storage in the first place. The dependency runs one way.

**What would resolve it**: GA support for an S3 Access Point as an External Location
target, which requires the generated session policy to handle Access Point ARNs.

---

## 2. `iceberg_rest` is not an accepted Connection Type

**Measured** 2026-05-31. [BLK-005](../en/blocker-tracker.md)

```sql
CREATE CONNECTION ... TYPE iceberg_rest ...
→ CONNECTION_TYPE_NOT_SUPPORTED
```

S3 Tables exposes a managed Iceberg REST Catalog endpoint. A Databricks SQL Warehouse
cannot consume it, because `iceberg_rest` is not in the supported connection types.
`TYPE GLUE` is not an alternative for this — it requires host, httpPath and a PAT,
which makes it Databricks-to-Databricks.

For comparison on the same endpoint: Athena reads it with zero configuration through
the Glue federated catalog, and PyIceberg and DuckDB read it directly. So the endpoint
itself is straightforward to consume.

### Workarounds, ranked by how well they hold up

| Option | Governance | Note |
|---|:---:|---|
| Glue HMS Federation (`CREATE CONNECTION TYPE glue`) | ✅ Unity Catalog applies | **The practical answer today.** Reference S3 Tables Iceberg tables as a Foreign Catalog via the Glue federated catalog. [Execution guide](../../integrations/iceberg-metadata-catalog/databricks/foreign-iceberg-execution-guide.md) |
| Iceberg on standard S3 → Glue Catalog → Foreign Catalog | ✅ Applies | Most reliable, but gives up S3 Tables' managed maintenance |
| Databricks Spark cluster with manual `spark.sql.catalog.s3tables` | ❌ Outside Unity Catalog | Technically equivalent to the EMR mechanism. **Untested here** (UNV-009) — inferred from the EMR result, no recorded run |
| Query via Athena or EMR instead | n/a | AWS-native engines work normally |

Because Glue HMS Federation exists and is GA, this is less severe than item 1. It is
a missing direct route rather than a missing capability.

---

## 3. Runtime seccomp blocks NFS/SMB mount

**Confirmed** 2026-05 as a design-level constraint. [BLK-007](../en/blocker-tracker.md)

The Databricks Runtime seccomp profile prohibits `mount` and `umount`, so a cluster
cannot mount NFS or SMB to reach FSx for ONTAP directly.

**Recorded as expected behaviour, not as a request.** This is intentional security
design and it is the correct default for a multi-tenant runtime. It is listed here
only so the reasoning is visible to anyone who finds the failure and wonders whether
to pursue it. The answer is no — use the network paths in item 1.

---

## What has not been tested

The Databricks workspaces used in May 2026 were torn down, so several cases have no
recorded run. Stated so this feedback is not read as more thorough than it is.

| Item | Note |
|---|---|
| Iceberg REST Catalog from a Databricks Spark cluster | UNV-009. Inferred from the EMR mechanism; no run |
| Executor-scale boto3 access from a customer-managed VPC | UNV-010. The Databricks-managed VPC case is recorded as failing on egress to FSx; the customer-managed VPC case is untested |
| 9 of the 11 cases in `verification-pack/databricks/test-cases.yaml` | UNV-011. No recorded run |
| Automated tests for the integration | UNV-012. `integrations/databricks/tests/` holds only `.gitkeep`. Snowflake has 8 test files; Databricks has none |

Note that item 1 blocks the Unity Catalog path regardless of what these would show.
