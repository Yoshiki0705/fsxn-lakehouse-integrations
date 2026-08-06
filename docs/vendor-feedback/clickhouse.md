🌐 **English** | [日本語](./clickhouse-ja.md)

# Feedback: ClickHouse

Scope: the `s3()` table function reading from an Amazon FSx for NetApp ONTAP S3 Access
Point. Measured 2026-05-26 on ClickHouse 26.5.1.
[Evidence](../../verification-pack/clickhouse/evidence/2026-05-26/evidence-record.yaml)

## Summary

One finding, and it is a credential-handling gap rather than a storage compatibility
gap. ClickHouse recognised the Access Point alias as a bucket name and the path-style
URL form worked. What blocked the test was that `s3()` has no way to accept an STS
session token, so temporary credentials cannot be used at all.

This is not specific to FSx for ONTAP. It applies to any S3 access from ClickHouse
using assumed-role credentials.

---

## The finding: `s3()` cannot accept an STS session token

Three approaches were attempted, all with STS temporary credentials.

| Attempt | Result |
|---|---|
| `SETTINGS s3_session_token = ...` | `UNKNOWN_SETTING: s3_session_token is neither a builtin setting` |
| Environment variable `AWS_SESSION_TOKEN` | `HTTP 400 Bad Request — Failed to get object info`. The environment variable was not picked up by `s3()` |
| Explicit `access_key` + `secret` from STS output | `HTTP 400` — STS credentials are invalid without the accompanying session token, and there is no parameter to pass it |

The third row is the core of it. STS issues three values, and `s3()` accepts two. The
first two rows are attempts to supply the third through other channels, and neither
route reaches the S3 client.

### What did work

Worth recording, because it narrows the problem to credentials alone:

| Observation | Detail |
|---|---|
| Path-style URL | `https://s3.<region>.amazonaws.com/<bucket>/<key>` was accepted |
| Access Point alias as bucket name | ClickHouse recognised it without special handling |

So the read path is plausible. Only authentication blocked it.

## Expected to work, untested

| Credential source | Reason it should work | Status |
|---|---|---|
| IAM user long-term access key | No session token involved. `s3('url', 'ACCESS_KEY', 'SECRET_KEY', 'Parquet')` | Untested (UNV-013) |
| EC2 Instance Profile via IMDS | ClickHouse supports IMDS, which supplies credentials without needing a token in the URL | Untested |
| ClickHouse Cloud with IAM role trust | Cross-account role assumption handled by the platform, not by `s3()` parameters | Untested |

None of these were run. No ClickHouse instance is currently deployed for this project,
and the Docker test used STS credentials because that is what was available. Listed as
expectations, not results.

## What would help

| Suggestion | Rationale |
|---|---|
| Add a session-token parameter or setting for `s3()` | Assumed-role credentials are the normal way to grant scoped, time-limited S3 access in AWS. Requiring long-term IAM user keys instead pushes users toward a credential type most AWS guidance discourages |
| If IMDS or a credentials provider chain is the intended answer, say so in the `s3()` documentation | The current documentation describes key and secret parameters, which reads as though those are the options. A note pointing at the provider chain for temporary credentials would redirect the attempt |

## Positioning note

This is recorded at low priority in this repository, and the reason is worth stating so
the ranking is not mistaken for a judgement about the product.

In the manufacturing use case where ClickHouse appears here, its role is real-time
quality analytics from Kafka — the hot path. Reading historical data from an FSx for
ONTAP S3 Access Point is a cold-path concern: batch enrichment and post-hoc analysis.
For the hot path, Materialized Views consuming directly from Kafka are the appropriate
design, and no S3 access is involved.

So the credential gap constrains a secondary use of ClickHouse in this architecture,
not its primary one. It is a genuine gap and worth closing, but it is not blocking the
role ClickHouse is chosen for.

Separately, [BLK-003](../en/blocker-tracker.md) means the `S3Queue` engine cannot
ingest directly from an Access Point, since that depends on S3 Event Notifications
which are not emitted. `S3Queue` against a standard S3 bucket fed by DataSync is the
available path, and is also untested here (UNV-015).

## Untested items

| ID | Item |
|---|---|
| UNV-013 | `s3()` reading Parquet directly from an FSx for ONTAP S3 Access Point with a working credential source |
| UNV-014 | `iceberg()` table function plus Glue Catalog integration (ClickHouse 23.8+) |
| UNV-015 | `S3Queue` ingesting from a standard S3 bucket fed by DataSync |
| — | ListObjectsV2 latency impact on `s3()` glob patterns. Note that the 30–80x figure this repository previously published was withdrawn after re-measurement at 0.9–1.4x for up to 5,000 objects |
