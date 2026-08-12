# Experimental validation notebook
# This notebook documents observed behavior for the Databricks FILE type (Beta) and the
# _object_metadata column against FSx for ONTAP S3 Access Points.
# It is not a production reference architecture.
# Every cell records the verbatim error on failure, because the failures are the evidence.
# Databricks notebook source
# MAGIC %md
# MAGIC # 10 - FILE type (Beta) and `_object_metadata` against FSx for ONTAP
# MAGIC
# MAGIC ## What this decides
# MAGIC
# MAGIC Two Databricks features changed the picture for unstructured data on FSx for ONTAP:
# MAGIC
# MAGIC 1. **FILE type (Beta)** — a Delta column holding a governed reference to a file.
# MAGIC    `FILE EXTERNAL` is documented as supported only for files **inside a Unity Catalog
# MAGIC    volume**, and a UC external volume cannot be created on an S3 Access Point
# MAGIC    ([BLK-001](../../../docs/en/blocker-tracker.md)). This notebook confirms whether that
# MAGIC    chain really terminates, or whether some path exists.
# MAGIC 2. **`_object_metadata`** (DBR 18.2+) — exposes S3 **object tags** and user-defined
# MAGIC    metadata as queryable columns. FSx for ONTAP S3 AP supports object tagging
# MAGIC    (verified 2026-08-12, see `verification-pack/s3ap-object-tagging/`). If
# MAGIC    `_object_metadata` works against an Access Point path, object-side metadata can be
# MAGIC    inherited into a metadata table. If it does not, the bridge is native-S3-only.
# MAGIC
# MAGIC Analysis and design context: [databricks-file-type-evaluation](../../../docs/en/databricks-file-type-evaluation.md)
# MAGIC
# MAGIC ## Prerequisites
# MAGIC
# MAGIC - **DBR 18 LTS or above** for FILE type; **DBR 18.2 or above** for `_object_metadata`
# MAGIC - FILE type is **Beta**: a workspace admin must enable it on the **Previews** page
# MAGIC - FILE type is **not supported on serverless notebooks** (works on notebooks attached
# MAGIC   to a serverless SQL warehouse)
# MAGIC - A UC catalog/schema you can create volumes and tables in
# MAGIC - For the Access Point cases: the S3 AP alias, and an IAM path that reaches it.
# MAGIC   `_object_metadata.tags` additionally needs `s3:GetObjectTagging` — without it `tags`
# MAGIC   returns `null` rather than failing, so a null result is ambiguous unless the
# MAGIC   permission is confirmed first.
# MAGIC
# MAGIC ## How to read the output
# MAGIC
# MAGIC Each case prints `PASS` / `FAIL` / `SKIP` and, on failure, the exception verbatim.
# MAGIC The final cell emits JSON to paste into
# MAGIC `verification-pack/databricks/file-type/evidence/<YYYY-MM-DD>/`.

# COMMAND ----------
# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------
# --- update these ---------------------------------------------------------------
CATALOG = "<your_catalog>"
SCHEMA = "file_type_probe"

# FSx for ONTAP S3 Access Point alias (no s3:// prefix)
S3AP_ALIAS = "<your-ap-alias-ext-s3alias>"
S3AP_PREFIX = "bronze/"          # a prefix that contains at least one readable file

# A native S3 path that IS a working UC external location, used as the control.
# Without a control, a failure on the Access Point cannot be attributed.
CONTROL_S3_PATH = "s3://<your-standard-bucket>/<prefix>/"

# Existing UC volume holding a few files, for the FILE EXTERNAL baseline.
# Leave as None to create a managed volume and upload a sample file.
EXISTING_VOLUME = None            # e.g. "/Volumes/main/default/my_volume/"
# -------------------------------------------------------------------------------

S3AP_PATH = f"s3://{S3AP_ALIAS}/{S3AP_PREFIX}"
FQ_SCHEMA = f"{CATALOG}.{SCHEMA}"
FILESPACE_VOLUME = f"/Volumes/{CATALOG}/{SCHEMA}/filespace/"

results = []


def record(case_id, name, status, detail="", error=None, verdict=""):
    """Record one case. `error` is stored verbatim — it is the evidence."""
    row = {
        "case_id": case_id,
        "name": name,
        "status": status,
        "detail": str(detail)[:2000],
        "error": None if error is None else str(error)[:2000],
        "verdict": verdict,
    }
    results.append(row)
    print(f"[{status}] {case_id}  {name}")
    if detail:
        print(f"        {str(detail)[:300]}")
    if error:
        print(f"        ERROR: {str(error)[:600]}")
    return row


def attempt(case_id, name, fn, verdict_pass="", verdict_fail=""):
    try:
        out = fn()
        return record(case_id, name, "PASS", detail=out, verdict=verdict_pass)
    except Exception as exc:  # noqa: BLE001 — the exception text is the deliverable
        return record(case_id, name, "FAIL", error=exc, verdict=verdict_fail)


# COMMAND ----------
# MAGIC %md
# MAGIC ## Case 0 — Environment: runtime version and feature availability
# MAGIC
# MAGIC Establishes whether a later failure means "not supported" or "not enabled here".

# COMMAND ----------
dbr = spark.conf.get("spark.databricks.clusterUsageTags.sparkVersion", "unknown")
record("DBX-FILE-000", "Databricks Runtime version", "PASS", detail=dbr,
       verdict="FILE type needs DBR 18 LTS+; _object_metadata needs DBR 18.2+")

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {FQ_SCHEMA}")

# Is the FILE type recognised by the parser at all? A syntax/feature error here means
# the Beta is not enabled on this workspace, which is different from S3 AP not working.
attempt(
    "DBX-FILE-001",
    "FILE type recognised (CREATE TABLE with FILE EXTERNAL column)",
    lambda: spark.sql(
        f"CREATE TABLE IF NOT EXISTS {FQ_SCHEMA}.probe_ext (id BIGINT, f FILE EXTERNAL)"
    ) and "created",
    verdict_pass="FILE type is available on this workspace",
    verdict_fail="FILE type unavailable — check DBR version and the Previews page before "
                 "interpreting any later result",
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Case 1 — Baseline: FILE EXTERNAL over a Unity Catalog volume
# MAGIC
# MAGIC The documented happy path. If this fails, nothing below is interpretable.

# COMMAND ----------
if EXISTING_VOLUME:
    volume_path = EXISTING_VOLUME
    record("DBX-FILE-010", "Volume for baseline", "PASS", detail=f"using {volume_path}")
else:
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {FQ_SCHEMA}.probe_vol")
    volume_path = f"/Volumes/{CATALOG}/{SCHEMA}/probe_vol/"
    dbutils.fs.put(f"{volume_path}sample.txt", "file type probe payload\n", overwrite=True)
    record("DBX-FILE-010", "Volume for baseline", "PASS",
           detail=f"created {volume_path} with sample.txt")

attempt(
    "DBX-FILE-011",
    "list_files over a UC volume",
    lambda: [r.asDict() for r in
             spark.sql(f"SELECT path, size FROM list_files('{volume_path}')").limit(5).collect()],
    verdict_pass="list_files works on volume paths",
)

attempt(
    "DBX-FILE-012",
    "CTAS: FILE EXTERNAL table from list_files over a volume",
    lambda: spark.sql(f"""
        CREATE OR REPLACE TABLE {FQ_SCHEMA}.docs_external AS
        SELECT path, size, file FROM list_files('{volume_path}')
    """) and spark.table(f"{FQ_SCHEMA}.docs_external").count(),
    verdict_pass="FILE EXTERNAL baseline works — later failures are path-specific",
)

attempt(
    "DBX-FILE-013",
    "Read FILE metadata fields with dot notation",
    lambda: [r.asDict() for r in spark.sql(f"""
        SELECT file.uri, file.size, file.content_type, file.checksum
        FROM {FQ_SCHEMA}.docs_external LIMIT 3
    """).collect()],
    verdict_pass="uri/size/content_type/checksum readable. Note: no tag field exists",
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Case 2 — The blocked chain: FILE EXTERNAL against an S3 Access Point
# MAGIC
# MAGIC Expected to fail. `list_files` is tried separately from storing a `FILE EXTERNAL`
# MAGIC reference, because the reference doc says `list_files` accepts an *external location*
# MAGIC path while `FILE EXTERNAL` storage is restricted to volumes. Those two could fail at
# MAGIC different points, and which one fails changes what to ask Databricks for.

# COMMAND ----------
attempt(
    "DBX-FILE-020",
    "list_files against an S3 Access Point path",
    lambda: [r.asDict() for r in
             spark.sql(f"SELECT path, size FROM list_files('{S3AP_PATH}')").limit(5).collect()],
    verdict_pass="list_files reaches the Access Point — narrows the gap to FILE storage only",
    verdict_fail="list_files cannot reach the Access Point (expected under BLK-001)",
)

attempt(
    "DBX-FILE-021",
    "list_files against the control native-S3 external location",
    lambda: [r.asDict() for r in
             spark.sql(f"SELECT path, size FROM list_files('{CONTROL_S3_PATH}')").limit(5).collect()],
    verdict_pass="control works — treat a DBX-FILE-020 failure as storage-target behaviour, "
                 "not a broken environment",
    verdict_fail="control also fails — fix the control before drawing conclusions",
)

attempt(
    "DBX-FILE-022",
    "Store a FILE EXTERNAL reference to an object on the S3 Access Point",
    lambda: spark.sql(f"""
        CREATE OR REPLACE TABLE {FQ_SCHEMA}.docs_s3ap AS
        SELECT path, size, file FROM list_files('{S3AP_PATH}')
    """) and spark.table(f"{FQ_SCHEMA}.docs_s3ap").count(),
    verdict_pass="UNEXPECTED — would mean FILE EXTERNAL works outside volumes. Re-verify",
    verdict_fail="Expected: FILE EXTERNAL is volume-only, and the Access Point cannot be a volume",
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Case 3 — FILE MANAGED and the FileSpace question
# MAGIC
# MAGIC `FILE MANAGED` needs a *FileSpace*, declared as a volume path in the
# MAGIC `databricks.filespace-preview` table property. The docs say "a Unity Catalog volume"
# MAGIC without stating whether it may be **external**. If an external FileSpace were allowed,
# MAGIC that would be a second theoretical route to ONTAP-resident bytes — still blocked by
# MAGIC BLK-001 today, but it changes what to ask for. Case 3.3 settles the question.

# COMMAND ----------
spark.sql(f"CREATE VOLUME IF NOT EXISTS {FQ_SCHEMA}.filespace")

attempt(
    "DBX-FILE-030",
    "CREATE TABLE with FILE MANAGED + managed-volume FileSpace",
    lambda: spark.sql(f"""
        CREATE OR REPLACE TABLE {FQ_SCHEMA}.docs_managed (id BIGINT, f FILE MANAGED)
        TBLPROPERTIES ('databricks.filespace-preview' = '{FILESPACE_VOLUME}')
    """) and "created",
    verdict_pass="FILE MANAGED baseline works",
)

attempt(
    "DBX-FILE-031",
    "Ingest a volume file into FILE MANAGED (copies bytes into UC storage)",
    lambda: spark.sql(f"""
        INSERT INTO {FQ_SCHEMA}.docs_managed
        SELECT row_number() OVER (ORDER BY path), file FROM list_files('{volume_path}')
    """) and spark.table(f"{FQ_SCHEMA}.docs_managed").count(),
    verdict_pass="Ingestion works. Note this is a COPY — zero-copy is forfeited",
)

attempt(
    "DBX-FILE-032",
    "CREATE TABLE with FILE MANAGED whose FileSpace is an EXTERNAL volume",
    lambda: spark.sql(f"""
        CREATE OR REPLACE TABLE {FQ_SCHEMA}.docs_managed_ext (id BIGINT, f FILE MANAGED)
        TBLPROPERTIES ('databricks.filespace-preview' = '{EXISTING_VOLUME or volume_path}')
    """) and "created — record whether the volume above is managed or external",
    verdict_pass="Answers Q4: an external volume is accepted as a FileSpace",
    verdict_fail="Answers Q4: FileSpace must be a managed volume",
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Case 4 — `_object_metadata`: the object-tag bridge
# MAGIC
# MAGIC This is the case that matters most for this repository. FSx for ONTAP S3 AP supports
# MAGIC object tags (verified). The question is whether Databricks can read them from an
# MAGIC Access Point path.
# MAGIC
# MAGIC The control on native S3 runs first. A `null` in `tags` is ambiguous — it means either
# MAGIC "no tags" or "missing `s3:GetObjectTagging`" — so the control must show non-null tags
# MAGIC for the Access Point result to mean anything. Tag the control objects first.

# COMMAND ----------
attempt(
    "DBX-FILE-040",
    "_object_metadata on the control native-S3 path (must show non-null tags)",
    lambda: [r.asDict() for r in spark.read.format("binaryFile")
             .load(CONTROL_S3_PATH)
             .selectExpr("_metadata.file_path as path",
                         "_object_metadata.etag as etag",
                         "_object_metadata.mime_type as mime_type",
                         "_object_metadata.tags as tags",
                         "_object_metadata.user_metadata as user_metadata")
             .limit(3).collect()],
    verdict_pass="Control established. If tags are null here, tag the control objects and re-run",
    verdict_fail="Control failed — check DBR 18.2+ and s3:GetObjectTagging",
)

attempt(
    "DBX-FILE-041",
    "_object_metadata on the FSx for ONTAP S3 Access Point path",
    lambda: [r.asDict() for r in spark.read.format("binaryFile")
             .load(S3AP_PATH)
             .selectExpr("_metadata.file_path as path",
                         "_object_metadata.etag as etag",
                         "_object_metadata.tags as tags",
                         "_object_metadata.user_metadata as user_metadata")
             .limit(3).collect()],
    verdict_pass="THE KEY RESULT — object tags on FSx for ONTAP are readable from Databricks. "
                 "Confirm tags are non-null, not merely that the read succeeded",
    verdict_fail="The object-tag bridge is native-S3-only for now. This error text is the "
                 "evidence for Q3",
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Case 5 — Sharing a table that contains a FILE column
# MAGIC
# MAGIC Volume sharing exists (`ALTER SHARE ... ADD VOLUME`). Whether a table carrying a
# MAGIC `FILE` column can be shared is documented neither way. Requires `CREATE SHARE`.

# COMMAND ----------
SHARE_NAME = "file_type_probe_share"

attempt(
    "DBX-FILE-050",
    "Add a FILE-column table to an OpenSharing share",
    lambda: (spark.sql(f"CREATE SHARE IF NOT EXISTS {SHARE_NAME}"),
             spark.sql(f"ALTER SHARE {SHARE_NAME} ADD TABLE {FQ_SCHEMA}.docs_external"),
             "added")[-1],
    verdict_pass="Answers Q5: a FILE-column table is accepted into a share. Recipient-side "
                 "recognition still needs a separate check",
    verdict_fail="Answers Q5: FILE-column tables are rejected by sharing",
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Results — paste into the evidence record

# COMMAND ----------
import json

summary = {
    "test_id": "DBX-FILE-TYPE-001",
    "date_tested": "<YYYY-MM-DD>",
    "databricks_runtime": dbr,
    "s3_access_point": S3AP_ALIAS,
    "control_path": CONTROL_S3_PATH,
    "counts": {
        s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "FAIL", "SKIP")
    },
    "cases": results,
}
print(json.dumps(summary, indent=2, default=str))

print("\n" + "=" * 70)
print("Key questions and what answered them:")
for cid, q in [
    ("DBX-FILE-022", "Can FILE EXTERNAL reference an S3 Access Point object?"),
    ("DBX-FILE-032", "Q4: may a FileSpace be an external volume?"),
    ("DBX-FILE-041", "Q3: can _object_metadata read object tags via an S3 AP?"),
    ("DBX-FILE-050", "Q5: can a FILE-column table be shared?"),
]:
    row = next((r for r in results if r["case_id"] == cid), None)
    print(f"  {cid}  {row['status'] if row else 'NOT RUN':6}  {q}")
    if row and row["verdict"]:
        print(f"           -> {row['verdict']}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Cleanup
# MAGIC
# MAGIC `FILE MANAGED` copied bytes into the FileSpace volume, and **automatic garbage
# MAGIC collection of unreferenced managed files is not supported in Beta**. Dropping the
# MAGIC table does not necessarily reclaim them, so check the FileSpace volume afterwards.

# COMMAND ----------
# Uncomment to clean up.
# spark.sql(f"DROP SHARE IF EXISTS {SHARE_NAME}")
# for t in ["probe_ext", "docs_external", "docs_s3ap", "docs_managed", "docs_managed_ext"]:
#     spark.sql(f"DROP TABLE IF EXISTS {FQ_SCHEMA}.{t}")
# print("Remaining files in the FileSpace volume (Beta has no automatic GC):")
# display(dbutils.fs.ls(FILESPACE_VOLUME))
# spark.sql(f"DROP VOLUME IF EXISTS {FQ_SCHEMA}.filespace")
# spark.sql(f"DROP VOLUME IF EXISTS {FQ_SCHEMA}.probe_vol")
