# Cleanup notes — Snowflake verification 2026-08-06

> **Status: done.** Everything listed here was removed on 2026-08-06 and the
> removal was verified: `SHOW EXTERNAL VOLUMES` returns 0 rows, the S3 bucket
> returns `NoSuchBucket`, and the IAM role returns `NoSuchEntity`. The commands
> are kept so the same setup can be torn down again if the verification is repeated.

Objects created during `SNOWFLAKE-S3AP-003`.

## Snowflake (database `FSXN_S3AP_VERIFY_DB`, schema `BRONZE`)

| Object | Type |
|---|---|
| `STAGE_FORMATS` | stage on the Access Point, `sfverify/formats/` |
| `STAGE_UNLOAD_SSE` | stage used for the unload attempt |
| `FF_JSON`, `FF_AVRO`, `FF_ORC` | file formats |
| `EXT_FMT_JSON` | external table (used to show the Dynamic Table constraint) |
| `FMT_LANDING` | standard table |
| `DT_FROM_AP` | dynamic table |
| `ICE_FROM_AP` | Managed Iceberg Table |
| `READ_STAGE_FILE` | Python UDF |
| `EV_ICEBERG_VERIFY` | external volume (account level) |

```sql
DROP DYNAMIC TABLE IF EXISTS BRONZE.DT_FROM_AP;
DROP ICEBERG TABLE  IF EXISTS BRONZE.ICE_FROM_AP;
DROP TABLE          IF EXISTS BRONZE.FMT_LANDING;
DROP EXTERNAL TABLE IF EXISTS BRONZE.EXT_FMT_JSON;
DROP FUNCTION       IF EXISTS BRONZE.READ_STAGE_FILE(STRING);
DROP STAGE          IF EXISTS BRONZE.STAGE_FORMATS;
DROP STAGE          IF EXISTS BRONZE.STAGE_UNLOAD_SSE;
DROP FILE FORMAT    IF EXISTS BRONZE.FF_JSON;
DROP FILE FORMAT    IF EXISTS BRONZE.FF_AVRO;
DROP FILE FORMAT    IF EXISTS BRONZE.FF_ORC;
DROP EXTERNAL VOLUME IF EXISTS EV_ICEBERG_VERIFY;
```

## AWS

| Resource | Identifier |
|---|---|
| S3 bucket (external volume) | `fsxn-sf-iceberg-verify-20260806` |
| IAM role | `fsxn-sf-iceberg-verify-role` |
| IAM inline policy | `fsxn-sf-iceberg-verify-policy` |
| Objects on the Access Point | `sfverify/formats/fmt_test.{json,avro,orc}`, `fmt_test2.json` |

The orphaned unload object `sfverify/formats/unload_probe_1/data_0_0_0.csv.gz`
was deleted during the session.

`sfverify/events/` was **not** touched — those four files belong to the earlier
Snowpipe verification recorded under
[`verification-pack/snowpipe-pattern-a/evidence/2026-08-06/`](../../../snowpipe-pattern-a/evidence/2026-08-06/),
as do the `RAW_EVENTS` table and the `STAGE_NO_APARN` / `STAGE_WITH_APARN` stages
that remain in `FSXN_S3AP_VERIFY_DB.BRONZE`.

```bash
aws s3 rm --recursive s3://fsxn-sf-iceberg-verify-20260806/
aws s3 rb s3://fsxn-sf-iceberg-verify-20260806
aws iam delete-role-policy --role-name fsxn-sf-iceberg-verify-role \
  --policy-name fsxn-sf-iceberg-verify-policy
aws iam delete-role --role-name fsxn-sf-iceberg-verify-role
AP=<access-point-alias>
aws s3 rm --recursive "s3://$AP/sfverify/formats/"
```

Drop the External Volume in Snowflake before deleting the bucket, otherwise the
volume is left pointing at storage that no longer exists.
