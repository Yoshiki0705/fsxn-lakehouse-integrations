# Documentation Request: FlexCache Write-Back XLD Behavior with S3 NAS Bucket Origin Writes

> **Finding ID**: FC-004
> **Target**: NetApp BU (ONTAP Documentation Team)
> **Priority**: Medium
> **Date**: 2026-07-21

---

## Use Case Description

FlexCache write-back mode enables low-latency writes at remote Cache Volumes. When the Origin Volume has an S3 NAS bucket configured (for FSx for ONTAP S3 Access Point access), writes arriving via S3 API directly to the Origin trigger XLD (Exclusive Lock Delegation) revoke on Cache Volumes holding dirty data for the same files.

This interaction is architecturally correct and functions as designed, but the specific behavior of S3 API writes triggering XLD revoke is not documented in the FlexCache write-back documentation. Customers designing architectures with both S3 AP ingestion and FlexCache write-back distribution need explicit documentation of this interaction.

---

## Impact Description

Without explicit documentation, customers may:
1. Design architectures where S3 AP ingestion and FlexCache write-back operate on overlapping file sets, unknowingly risking Cache dirty data loss
2. Spend troubleshooting time investigating "unexpected" data loss when S3 AP writes cause XLD revoke
3. Misattribute the behavior to a bug rather than a designed consistency mechanism

**Specific scenario:**
- Origin Volume has S3 AP for automated data ingestion (IoT, batch ETL)
- Cache Volume uses write-back mode for local editing by remote teams
- If both access the same files: Cache dirty data is overwritten by Origin's version after XLD revoke

---

## Current Workaround

Design guidelines (derived from Phase 3 validation):

| Scenario | Risk | Recommendation |
|---------|------|----------------|
| S3 AP write (Origin) only + Cache read-only | Safe | Recommended pattern |
| Cache write (NFS/SMB) only + S3 AP read-only | Safe | Standard write-back use case |
| S3 AP write + Cache write on different files | Safe | File-level XLD protects per-file |
| S3 AP write + Cache write on same file | Data loss risk | Avoid by design |

---

## Proposed Documentation Enhancement

Add a section to the [FlexCache write-back guidelines](https://docs.netapp.com/us-en/ontap/flexcache-writeback/flexcache-write-back-guidelines.html) that explicitly describes:

1. **S3 NAS bucket (S3 API) writes as Origin-direct writes**: Clarify that S3 API writes to an Origin Volume with S3 NAS bucket configured are treated the same as any other Origin-direct write — they trigger XLD revoke on Cache Volumes holding dirty data for affected files.

2. **Data flow diagram for S3 AP + write-back interaction**:
   ```
   S3 AP write to Origin
     → Origin detects conflicting XLD on Cache
     → XLD revoke sent to Cache
     → Cache dirty data discarded (Origin version wins)
     → S3 AP write committed to Origin
     → Cache fetches updated data on next access (after TTL)
   ```

3. **Design guidance table**: Document the safe/unsafe combinations (as shown in the workaround section above).

4. **Existing documentation gap**: The current [FlexCache write-back architecture](https://docs.netapp.com/us-en/ontap/flexcache-writeback/flexcache-write-back-architecture.html) page documents that "writes to the origin will cause the exclusive lock to be revoked" but does not explicitly mention S3 API / S3 NAS bucket writes as a trigger for this mechanism.

---

## Reproduction Steps

```bash
# Environment: ONTAP 9.17.1, FlexCache write-back enabled

# 1. Create Origin Volume with S3 NAS bucket (via FSx for ONTAP S3 AP)
# 2. Create FlexCache Cache Volume with write-back enabled
# 3. Write file via NFS on Cache Volume (establishes XLD)
#    echo "cache data" > /mnt/cache/test-file.txt
# 4. Write to same file via S3 API on Origin
#    aws s3api put-object --bucket <s3-nas-bucket> --key test-file.txt --body new-data.txt
# 5. Observe: Cache dirty data for test-file.txt is revoked
# 6. Read from Cache after TTL: shows Origin's version (S3 AP write)

# Expected: This is correct behavior, but customers need documentation
# to design around it proactively
```

---

## Environment Information

| Item | Value |
|------|-------|
| ONTAP Version | 9.17.1P7D1 |
| FlexCache Mode | Write-back (enabled via `volume flexcache config modify -writeback-mode all`) |
| S3 AP Type | S3 NAS bucket (multiprotocol) |
| Validation | Phase 3, TC-03 and TC-05 (PASS — behavior confirmed as expected) |

---

## Supporting Evidence

| Source | Key Statement |
|--------|--------------|
| [NetApp Docs: FlexCache write-back architecture](https://docs.netapp.com/us-en/ontap/flexcache-writeback/flexcache-write-back-architecture.html) | "If data is written at the origin, the exclusive lock is revoked... the data in the cache will be invalidated" |
| [NetApp Docs: FlexCache write-back guidelines](https://docs.netapp.com/us-en/ontap/flexcache-writeback/flexcache-write-back-guidelines.html) | Lists supported/unsupported features but does not mention S3 NAS bucket interaction |
| Phase 3 Validation | TC-03/TC-05 confirmed S3 AP Origin write triggers XLD revoke on Cache (internal evidence) |

---

## Classification Note

This is a **documentation enhancement request**, not a product change request. The behavior itself is correct and consistent with FlexCache's XLD design. The request is to make this specific interaction (S3 API writes as XLD revoke trigger) explicitly documented so that architects can design appropriately from the outset.
