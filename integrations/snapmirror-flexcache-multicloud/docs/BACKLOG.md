# Backlog — S3 AP + SnapMirror + FlexCache Multi-Cloud

> 残課題と今後のアクション。優先度順に整理。

## In Progress

(なし — 現在進行中のタスクはありません)

## Ready (No Blocker)

| # | Task | Priority | Effort | Notes |
|:-:|------|:--------:|:------:|-------|
| 1 | EN demo guide prose — remaining ~400 lines of Japanese in code comments | P2 | 2h | Shell コメント内の日本語。主要散文は翻訳済み |
| 2 | Screenshot/recording capture during next execution | P2 | 1h | TC-09 再実行時に同時取得 |
| 3 | FlexCache cross-region E2E test (data write → NFS read in Region B) | P1 | 2h | Cluster Peering は validated。SVM Peering + FlexCache + NFS read が未完了 |
| 4 | SnapMirror cross-region test (Guide 07: break → S3 AP re-attach in Region B) | P1 | 2h | FSx B 再作成が必要 (~$6) |
| 5 | dev.to 記事化 (Part N: S3 AP + FlexCache マルチクラウド配信) | P1 | 4h | stakeholder-briefs/03 ベース |
| 6 | git commit + PR | P1 | 30min | 全成果物を feat/ ブランチで push |

## Requires External Action

| # | Task | Dependency | Notes |
|:-:|------|-----------|-------|
| 7 | CVO on GCP validation (Guide 04/09) | GCP account + CVO license | ~$20/test |
| 8 | CVO on Azure validation (Guide 05/10) | Azure account + CVO license | ~$20/test |
| 9 | GCNV validation (Guide 06/11) | GCNV access (GA) | Google Cloud |
| 10 | On-premises validation (Guide 03/08) | Physical ONTAP or AFF-C190 | Lab access |
| 11 | Windows EC2 SMB validation with screenshots | AD + Windows AMI | ~$5 |
| 12 | ONTAP 9.18.1 upgrade → FC-002 validation (S3 AP on FlexCache Cache) | FSx for ONTAP 9.18.1 adoption | Future |

## Completed (This Sprint)

| Task | Date |
|------|------|
| Phase 1-4 Research + Documentation + Validation + Communication | 2026-07-21 |
| TC-09: Lambda → S3 AP → FlexCache NFS + SMB (ALL PASS) | 2026-07-21 |
| IaC template (CFn + companion scripts) | 2026-07-21 |
| 12 Demo Guides (JA/EN) with Mermaid diagrams | 2026-07-21 |
| EN research.md full expansion (298→630 lines) | 2026-07-21 |
| FC-002 reclassification (ONTAP 9.18.1 S3 on FlexCache Cache) | 2026-07-21 |
| Feature Requests × 3 + Stakeholder Briefs × 4 | 2026-07-21 |
| Automated deploy/validate/teardown script (tc09) | 2026-07-21 |
| Cross-region deploy script (VPC + Peering + FSx B) | 2026-07-21 |
| AD CFn template fix (Description > 1024, Tags unsupported) | 2026-07-21 |
| FlexCache API finding (use_tiered_aggregate, correct endpoint) | 2026-07-21 |
| .gitignore update (params.env, state files) | 2026-07-21 |
| **Cross-region Cluster Peering VALIDATED (ap-northeast-1 ↔ us-west-2)** | 2026-07-21 |
| Old FlexCache Technical Debt cleaned (TC-03/TC-05 remnants) | 2026-07-21 |
| VPC Peering + routing lesson learned (subnet-specific RT) | 2026-07-21 |

## Technical Debt

| Item | Location | Impact | Status |
|------|----------|--------|:------:|
| ~~Old TC-03/TC-05 FlexCache volumes on svm_dest~~ | ~~fs-09ffe72a3b2b7dbbd~~ | ~~Storage cost~~ | ✅ Cleaned |
| ~~FSx B (us-west-2) deletion~~ | ~~fs-0c841c930edca14fd~~ | — | ✅ Deleted |
| ~~VPC B resources (VPC, Subnet, SG) in us-west-2~~ | ~~vpc-0287c0a9aa5f59cdd~~ | — | ✅ Deleted |
| Old SnapMirror relationship (s3ap_snapmirror_tc01) not fully released | fs-09ffe72a3b2b7dbbd / svm_dest | Minor (metadata only) | Low priority |

## Key Learnings (For Future Reference)

1. **FlexCache on FSx for ONTAP**: Use `/api/storage/flexcache/flexcaches` endpoint, NOT `/api/storage/volumes`. Include `use_tiered_aggregate: true` (FabricPool aggregate).
2. **fsxadmin password**: Resets via FSx API take 30-60s to propagate. Use Secrets Manager retrieval pattern, not inline passwords.
3. **FlexCache deletion**: Must remove junction path (`nas.path: ""`) BEFORE deleting via API.
4. **S3 AP FileSystemIdentity**: Use `root` for default SVMs. `fsxadmin` may not exist as a UNIX user.
5. **AD OU path for AWS Managed AD**: `OU=Computers,OU=<ShortName>,DC=<parts>` (includes intermediate OU).
6. **FlexCache write-back flush**: 30-90 seconds for Cache writes to appear at Origin (S3 AP).
7. **VPC Peering cross-region**: Requires explicit `accept` even for same-account (different from same-region).
8. **CFn Description limit**: 1024 characters max. Use `>-` for single-line folding.
9. **AWS::DirectoryService::MicrosoftAD**: Does NOT support `Tags` property in CloudFormation.
10. **ONTAP job retention**: Jobs expire within seconds after completion. Poll immediately after submission.
11. **VPC Peering route tables**: Adding a route to the main RT does NOT affect subnets using explicit RT associations. Check EC2 subnet's RT and add route there specifically.
12. **Cross-region FSx deletion order**: Delete SVM first, wait for completion, then delete file system. Cannot delete FS with SVMs.
13. **FlexCache write-back deletion**: Must disable `writeback.enabled` (PATCH to false) BEFORE deleting the FlexCache volume.
14. **Cross-region Cluster Peering**: Works between FSx for ONTAP in different AWS regions via VPC Peering. Confirmed `available` status (ap-northeast-1 ↔ us-west-2).
