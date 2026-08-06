🌐 **English** | [日本語](./README-ja.md)

# Vendor Feedback

Findings from this repository's verification runs, written up per vendor so each one
can be read and acted on independently.

## What these documents are

Each page states what was measured, what the measurement means for people building
on the product, and what would resolve the gap. Every item cites an evidence record
under [`verification-pack/`](../../verification-pack/) or names the layer where the
observation was made.

These are engineering observations, not complaints and not a ranking. Where a gap
exists, the trade-off is stated for the alternative as well. Where a product behaves
correctly and this repository previously said otherwise, the correction is recorded
on the same page.

## Pages

| Vendor / project | Items | Most significant finding |
|---|:---:|---|
| [AWS](./aws.md) | 7 | Two API gaps produce residue rather than clean refusals, so a failed statement can leave objects on the Access Point |
| [NetApp](./netapp.md) | 3 | Capabilities that ONTAP implements are not reachable through the FSx managed service, and the name-service dependency puts an AD outage in the S3 data path |
| [Databricks](./databricks.md) | 3 | An Access Point cannot be a Unity Catalog External Location, which removes governance from the zero-copy path entirely |
| [Snowflake](./snowflake.md) | 3 | Unload to an Access Point fails after the object has landed. Also the correction of a wrong explanation this repository published |
| [Apache Iceberg](./apache-iceberg.md) | 1 | S3FileIO does not handle an Access Point alias during metadata write, while Athena's Iceberg implementation on the same storage succeeds |
| [ClickHouse](./clickhouse.md) | 1 | `s3()` cannot accept an STS session token, so temporary credentials are unusable |

## Ground rules for these pages

| Rule | Reason |
|---|---|
| No support case numbers, engineer names, or internal ticket IDs | These are public documents |
| Verbatim error strings where recorded | An exact string is searchable and reproducible; a paraphrase is not |
| Inference labelled as inference | One item (Hudi) is a deduction, not a measurement. It says so |
| Withdrawn claims kept, not deleted | A claim that failed to reproduce is a result. Removing it silently would make the record less trustworthy, not more |
| Alternatives described with their own trade-offs | A gap in one product is not an argument for another |

## Status of what has been raised

| Vendor | Item | Raised | Current state |
|---|---|---|---|
| AWS | Conditional writes on FSx for ONTAP S3 AP | 2026-05 | Filed, no response |
| AWS | S3 Event Notifications on FSx for ONTAP S3 AP | 2026-05 | Filed, no response |
| AWS | Enable SnapMirror S3 on FSx for ONTAP | 2026-05 | Filed, no response |
| AWS | ListObjectsV2 latency | 2026-05 | Confirmed as a product characteristic. **Superseded** — the 30–80x figure did not reproduce on re-measurement (2026-08-05) |
| AWS | Lake Formation column-level permissions on S3 Tables federated catalogs | 2026-05 | Identified, not yet filed |
| Databricks | Unity Catalog External Location support for S3 Access Points | 2026-05 | Support case closed as not entitled (support tier). Raised in the community forum instead |
| Databricks | `iceberg_rest` as a Connection Type | 2026-05 | Support case closed as not entitled (support tier) |
| Databricks | OpenSharing STS credential vending on S3 Access Points | 2026-06 | Community forum, seeking architecture guidance |
| Snowflake | S3 Tables Iceberg REST endpoint as an External Catalog source | 2026-05 | Filed |
| Snowflake | Unload checksum validation against `aws:fsx` encryption | 2026-08 | Not yet filed — measured 2026-08-06 |
| Apache Iceberg | S3FileIO handling of Access Point aliases | — | Not yet filed |

> The two Databricks cases were closed for support-tier reasons rather than on technical
> merit, so the underlying questions remain open. They were moved to the public
> community forum, which is linked from the [blocker tracker](../en/blocker-tracker.md).

## Related reading

| Page | Purpose |
|---|---|
| [Known challenges by layer](../en/known-challenges.md) | The same findings organised by where they originate |
| [Blocker tracker](../en/blocker-tracker.md) | Status and workaround per known failure |
| [Unverified inventory](../en/unverified-inventory.md) | What has not been tested, and what it would take |
| [Compatibility matrix](../en/compatibility-matrix.md) | Per-engine, per-operation reference |
