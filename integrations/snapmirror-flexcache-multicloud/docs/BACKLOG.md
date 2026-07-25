# Backlog — S3 AP + SnapMirror + FlexCache Multi-Cloud

> 残課題と今後のアクション。優先度順に整理。

## Validation Status System

All 12 demo guides now include a validation status banner:

| Badge | Meaning | Script Available |
|:-----:|---------|:----------------:|
| ✅ **E2E validated** | Tested in live environment with evidence | Yes (executable) |
| ⚠️ **Partially validated** | Some steps confirmed, E2E incomplete | Yes (executable for completed parts) |
| ⚠️ **Procedure-level** | Commands based on documentation; not yet run E2E | Yes (template with TODOs) |

### Current Status Matrix

| Guide | Target | Status | Script |
|:-----:|--------|:------:|--------|
| 01 | FlexCache same-region (FSx→FSx) | ✅ Validated (TC-09, 2026-07-21) | `tc09-deploy-validate-teardown.sh` |
| 02 | FlexCache cross-region (FSx→FSx) | ✅ Validated (2026-07-22) | `cross-region-deploy.sh` + `cross-region-test.sh` |
| 03 | FlexCache on-premises | ⚠️ Procedure-level | `on-premises-test.sh` (template) |
| 04 | FlexCache CVO GCP | ⚠️ Procedure-level | `cvo-gcp-test.sh` (template) |
| 05 | FlexCache CVO Azure | ⚠️ Procedure-level | `cvo-azure-test.sh` (template) |
| 06 | FlexCache GCNV | ⚠️ Procedure-level | `gcnv-test.sh` (template) |
| 07 | SnapMirror cross-region | ✅ Validated (2026-07-22) | `cross-region-deploy.sh` + `cross-region-test.sh` |
| 08 | SnapMirror on-premises | ⚠️ Procedure-level | `on-premises-test.sh` (template) |
| 09 | SnapMirror CVO GCP | ⚠️ Procedure-level | `cvo-gcp-test.sh` (template) |
| 10 | SnapMirror CVO Azure | ⚠️ Procedure-level | `cvo-azure-test.sh` (template) |
| 11 | SnapMirror GCNV | ⚠️ Procedure-level | `gcnv-test.sh` (template) |

## In Progress

(なし — 現在進行中のタスクはありません)

## Ready (No Blocker)

| # | Task | Priority | Effort | Notes |
|:-:|------|:--------:|:------:|-------|
| 1 | EN demo guide prose — remaining ~400 lines of Japanese in code comments | P2 | 2h | Shell コメント内の日本語。主要散文は翻訳済み |
| 2 | Screenshot/recording capture during next execution | P2 | 1h | TC-09 再実行時に同時取得 |
| 3 | ~~FlexCache cross-region E2E test (data write → NFS read in Region B)~~ | ~~P1~~ | ~~2h~~ | ✅ Completed 2026-07-22. Cluster Peering + SVM Peering + FlexCache + NFS read/write validated (ap-northeast-1 → us-west-2). Data propagation <3s. |
| 4 | ~~SnapMirror cross-region test (Guide 07: break → S3 AP re-attach in Region B)~~ | ~~P1~~ | ~~2h~~ | ✅ Completed 2026-07-22. SnapMirror transfer + break + S3 AP re-attach ALL PASS. RTO ~3 min. New findings: SM-VAL-008/009/010/011. |
| 5 | dev.to 記事化 (Part N: S3 AP + FlexCache マルチクラウド配信) | P1 | 4h | stakeholder-briefs/03 ベース |
| 6 | git commit + PR | P1 | 30min | 全成果物を feat/ ブランチで push |

## Requires External Action

| # | Task | Dependency | Script | Notes |
|:-:|------|-----------|--------|-------|
| 7 | CVO on GCP validation (Guide 04/09) | GCP account + CVO license | `cvo-gcp-test.sh` | ~$20/test |
| 8 | CVO on Azure validation (Guide 05/10) | Azure account + CVO license | `cvo-azure-test.sh` | ~$20/test |
| 9 | GCNV validation (Guide 06/11) | GCNV access (GA) | `gcnv-test.sh` | Google Cloud |
| 10 | On-premises validation (Guide 03/08) | Physical ONTAP or AFF-C190 | `on-premises-test.sh` | Lab access |
| 11 | Windows EC2 SMB validation with screenshots | AD + Windows AMI | — | ~$5 |
| 12 | ONTAP 9.18.1 upgrade → FC-002 validation (S3 AP on FlexCache Cache) | FSx for ONTAP 9.18.1 adoption | — | Future |
| 13 | ONTAP 9.18.1 検証完了後 → FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns の互換性テーブル更新を依頼 | FC-002 検証完了 | — | あちらの Kiro から更新依頼待ちの合意あり |

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
| **Cross-region FlexCache E2E VALIDATED (Origin write → Cache read <3s)** | 2026-07-22 |
| Cross-region teardown completed (FlexCache + peerings + FSx B deleted) | 2026-07-22 |
| Validation Status banners added to all 12 demo guides (EN+JA) | 2026-07-22 |
| Validation script templates created for all targets (on-prem, CVO GCP/Azure, GCNV) | 2026-07-22 |
| **SnapMirror cross-region E2E VALIDATED (transfer + break + S3 AP re-attach in us-west-2)** | 2026-07-22 |
| SM-VAL-008/009/010/011 findings documented in research.md | 2026-07-22 |
| Safe teardown script (`cross-region-teardown.sh`) with SM-VAL-011 order | 2026-07-22 |
| FSx B MISCONFIGURED resolved via ONTAP CLI (snapmirror release + vserver peer delete) | 2026-07-22 |

## Technical Debt

| Item | Location | Impact | Status |
|------|----------|--------|:------:|
| ~~Old TC-03/TC-05 FlexCache volumes on svm_dest~~ | ~~Region A cluster~~ | ~~Storage cost~~ | ✅ Cleaned |
| ~~FSx B (us-west-2) deletion~~ | ~~us-west-2~~ | — | ✅ Deleted |
| ~~VPC B resources (VPC, Subnet, SG) in us-west-2~~ | ~~us-west-2~~ | — | ✅ Deleted |
| Old SnapMirror relationship (s3ap_snapmirror_tc01) not fully released | Region A cluster / svm_dest | Minor (metadata only) | Low priority |
| **FSx B (us-west-2) SVM MISCONFIGURED — blocks FS deletion** | Region B cluster | — | ✅ Resolved via ONTAP CLI: `snapmirror release -force` + `vserver peer delete` from source side |
| Orphaned SVM peer records on Region A (3 zombie entries) | Region A cluster | None (metadata noise) | Low priority — will resolve when FSx B is deleted |

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
15. **FlexCache cross-region data propagation**: New files written to Origin via NFS appear in Cache Volume within 3 seconds (tested ap-northeast-1 → us-west-2, ~120ms RTT). No explicit cache refresh needed.
16. **Teardown order for cross-region FlexCache**: (1) Unmount NFS clients, (2) Remove junction path on FlexCache, (3) DELETE `/api/storage/flexcache/flexcaches/{uuid}`, (4) Delete Origin volume (may need `force=true` if cluster peering already removed), (5) Delete SVM Peering, (6) Delete Cluster Peering, (7) Delete SVM via FSx API, (8) Delete File System via FSx API. Deleting cluster peering before FlexCache causes orphaned origin relationships requiring `force=true`.
17. **Passphrase shell escaping in SSM**: Avoid `$` in Cluster Peering passphrases when executing via SSM send-command. Use alphanumeric-only passphrases (e.g., `CrossRegion2026Peer`) to prevent shell expansion issues.
18. **Critical teardown order (cross-region)**: NEVER delete VPC Peering/routes before confirming SVM peer deletion (`num_records: 0` on BOTH clusters). The SVM peer deletion protocol is two-phase and requires bidirectional connectivity. Violating this creates permanent zombie SVM peer records that block SVM/FS deletion and require AWS Support intervention (`vserver peer delete -force` via CLI, not exposed to fsxadmin REST API).
19. **FSx API VolumeType:DP lag (cross-region)**: After SnapMirror break, FSx API shows `OntapVolumeType: DP` for >10 minutes. S3 AP attachment succeeds regardless — the check is at ONTAP level. Don't use FSx API VolumeType as a gate.
20. **DP volumes for S3 AP re-attach**: Prefer `aws fsx create-volume --ontap-configuration '{"OntapVolumeType":"DP"}'` for immediate FSx API visibility. ONTAP REST API-created volumes (including FlexCache) take ~30 minutes to propagate to the FSx control plane. Once propagated, S3 AP can be attached normally.
21. **S3 AP re-attach RTO (cross-region)**: ~3 minutes total (break instant + junction path propagation ~2min + S3 AP creation ~30s + first API call ~30s). Same-region expected ~2 minutes.
22. **ONTAP CLI (SSH) for peer deletion**: When REST API `DELETE /api/svm/peers` returns 202 but records persist, use ONTAP CLI via SSH: `sshpass -p <pass> ssh fsxadmin@<mgmt-ip> "vserver peer delete -vserver <local> -peer-vserver <remote>"`. The CLI triggers the two-phase protocol correctly from either side. Always run from the SOURCE side first. Note: SSH access must be enabled on the FSx file system (Settings → Administrative Endpoints → enable SSH). This is not enabled by default on all deployments.
23. **SnapMirror release required before SVM peer delete**: If SnapMirror destination references exist, `vserver peer delete` fails with "Relationship is in use by SnapMirror". Run `snapmirror release -destination-path <dest> -source-path <src> -force true` from the SOURCE cluster first. See also: SM-VAL-011 in `docs/en/research.md` for the complete validated teardown order.
24. **FlexCache 削除は ONTAP REST API を使う**: FlexCache は ONTAP REST API (`DELETE /api/storage/flexcache/flexcaches/{uuid}`) で削除する。FSx API の `delete-volume` では「既に削除された」または「削除できない」状態になる場合がある。ONTAP で削除後、FSx API にゴーストエントリが残った場合は `delete-volume` で別途削除可能。
25. **FlexCache 削除後の FSx API ゴーストエントリ**: ONTAP REST API で FlexCache を削除しても、FSx API (`describe-volumes`) には fsvol-* エントリがしばらく残る。SVM 削除時に「non-root volumes exist」エラーが出る場合は、FSx API 経由で `delete-volume` を実行してゴーストを解消する。
26. **FSx for ONTAP S3 AP は FlexCache Volume に アタッチ不可（2026-07-24 検証）**: ONTAP 9.18.1P3D1 環境で検証。ONTAP ネイティブの S3 NAS bucket は FlexCache Cache で 9.18.1 からサポートだが、FSx for ONTAP S3 Access Points は FlexCache への アタッチを FSx マネージドレイヤーで明示的にブロックする。エラー: `Amazon FSx is unable to attach S3access point because the volume is a FlexCache.`
27. **FlexGroup + S3 AP は正常に動作する**: FlexGroup ボリューム（FLEXGROUP VolumeStyle）に S3 AP を正常にアタッチ可能。PutObject / ListObjectsV2 ともに動作確認済み（ONTAP 9.18.1P3D1, us-west-2, 2026-07-24）。FlexCache の Origin を FlexGroup にする構成でも Origin 側の S3 AP は問題なく機能する。
