# Instaclustr On-Premises PoC Setup Progress

> **Status**: VM host ready; awaiting Instaclustr internal documentation approval + VM images
> **Date**: 2026-06-15 (updated)
> **Team**: Japan-Auto/MFG Instaclustr Edge PoC
> **Instaclustr Contact**: Justin (justing@netapp.com)

---

## Infrastructure Ready

| Component | Details | Status |
|-----------|---------|--------|
| VM Host | ESXi 8.0 Update3 (DL380G10) | ✅ Ready |
| Internal Drive | 1TB (for ClickHouse) | ✅ Available |
| Failure Domain | None (PoC single-node) | ✅ N/A |
| Backup Storage | FAS2750 via ONTAP S3 | 🔄 Setting up new SVM |
| Network | Zero inbound constraints | ✅ Confirmed |
| Instaclustr Trial Account | Created | ✅ Active |
| Account ID | 76d65fad-1692-4178-9089-8c0a3f59cbfc | ✅ |
| Justin invited | justing@netapp.com | ✅ |

## Pending Items

| Item | Owner | Blocker |
|------|-------|---------|
| PoC documentation (specifics tests) | Justin | Internal approval |
| VM images (pre-configured virtual disks) | Justin | Documentation approval |
| ONTAP S3 SVM setup (backup target) | Itani | In progress |
| Gateway server setup | Itani | Needs VM images |

## Timeline

- **PoC duration**: 2-4 weeks (flexible based on business requirements)
- **Start**: After documentation approved + VM images provided
- **Backup protocol**: S3-compatible (ONTAP S3 on FAS2750)

## Key Decisions

1. **Backup to ONTAP S3** (not NFS) — Justin confirmed S3-compatible storage is acceptable
2. **Single-node PoC** — No failure domain topology (acceptable for PoC)
3. **On-prem only option greyed out** in trial — expected, will be enabled after internal process

## Chat History Summary

| Date | Event |
|------|-------|
| Initial | VM host specifications shared with Justin |
| Follow-up | Backup protocol changed from NFS to S3 (ONTAP S3) |
| Follow-up | Justin will write PoC documentation with specific tests |
| Follow-up | Itani creating new SVM on FAS2750 for ONTAP S3 |
| Follow-up | Instaclustr trial account created, Justin invited |
| Follow-up | Account ID shared (76d65fad-...) |

## Next Steps

1. Wait for Justin's PoC documentation (internal approval)
2. Complete ONTAP S3 SVM setup on FAS2750
3. Receive VM images from Instaclustr
4. Deploy gateway server + Kafka/ClickHouse VMs
5. Configure replication between on-prem Kafka and AWS (future)

## Confidentiality Note

No internal team member names, customer names, or company-specific identifiers are included. Only generic role descriptions and publicly available vendor contact information.
