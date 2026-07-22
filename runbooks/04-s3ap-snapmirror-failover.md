# S3 AP SnapMirror Failover — Operational Runbook

> FSx for ONTAP S3 AP アタッチ済みボリュームの SnapMirror フェイルオーバー手順

## Overview

FSx for ONTAP S3 Access Point（S3 AP）アタッチ済みボリュームをソースとする SnapMirror 関係のフェイルオーバー（break）後、デスティネーションで S3 AP アクセスを再開するための手順。

**前提**: Phase 3 検証（TC-01, TC-02）で動作確認済み。ONTAP 9.17.1P7D1。

## Prerequisites

- SnapMirror Asynchronous relationship が正常に動作していたこと
- デスティネーション SVM に `vserver object-store-server` が存在しないこと
- 適切な IAM 権限（`fsx:CreateAndAttachS3AccessPoint`, `s3:*` on AP ARN）

## Procedure

### Step 1: SnapMirror Break

```bash
# SnapMirror 関係を break（デスティネーションを RW に昇格）
curl -sk -u "fsxadmin:${FSX_PASSWORD}" \
  -X PATCH "https://${MGMT_IP}/api/snapmirror/relationships/${SM_REL_UUID}" \
  -H 'Content-Type: application/json' \
  -d '{"state": "broken_off"}'

# 確認: state = broken_off, healthy = true
curl -sk -u "fsxadmin:${FSX_PASSWORD}" \
  "https://${MGMT_IP}/api/snapmirror/relationships/${SM_REL_UUID}?fields=state,healthy"
```

### Step 2: Junction Path 設定

```bash
# DP ボリュームには junction path がない場合がある — 設定する
curl -sk -u "fsxadmin:${FSX_PASSWORD}" \
  -X PATCH "https://${MGMT_IP}/api/storage/volumes/${DST_VOL_UUID}" \
  -H 'Content-Type: application/json' \
  -d '{"nas": {"path": "/<volume-name>"}}'
```

### Step 3: FSx API 同期待機（~60秒）

```bash
# FSx API が junction path の変更を反映するまで待機
for i in $(seq 1 12); do
  JP=$(aws fsx describe-volumes --volume-ids ${DST_VOL_ID} \
    --query 'Volumes[0].OntapConfiguration.JunctionPath' --output text)
  [ "${JP}" != "None" ] && [ "${JP}" != "" ] && break
  echo "Waiting for FSx API sync... (${i}/12)"
  sleep 10
done
```

### Step 4: S3 AP 作成・アタッチ

```bash
aws fsx create-and-attach-s3-access-point \
  --name "${AP_NAME}" \
  --type ONTAP \
  --ontap-configuration '{
    "VolumeId": "'${DST_VOL_ID}'",
    "FileSystemIdentity": {
      "Type": "UNIX",
      "UnixUser": {"Name": "'${UNIX_USER}'"}
    }
  }' \
  --region ${REGION}
```

### Step 5: S3 AP 利用可能確認

```bash
# Lifecycle = AVAILABLE を確認
for i in $(seq 1 12); do
  LC=$(aws fsx describe-s3-access-points \
    --filters "Name=volume-id,Values=${DST_VOL_ID}" \
    --region ${REGION} \
    | jq -r '.S3AccessPoints[0].Lifecycle')
  [ "${LC}" = "AVAILABLE" ] && echo "S3 AP ready" && break
  sleep 10
done

# データアクセス確認
aws s3api list-objects-v2 --bucket "${DST_AP_ARN}" --max-keys 5
```

## Timing

| Step | Duration |
|------|:--------:|
| SnapMirror break | ~5s |
| Junction path set | ~5s |
| FSx API sync | ~60s |
| S3 AP creation | ~60s |
| **Total** | **~2.5 min** |

## Important Notes

- S3 AP はソースからデスティネーションに「移行」されない — デスティネーションで**新規作成**する
- S3 AP alias は新しい値になるため、利用側アプリケーションの AP ARN/alias 更新が必要
- IAM ポリシーも別途構成が必要（AWS レイヤーの認可は ONTAP レプリケーションに含まれない）
- FSx API の `OntapVolumeType` は break 後も一時的に `DP` と表示されるが、S3 AP 作成は成功する

## Rollback (Resync)

```bash
# SnapMirror resync（DP 状態に戻す）
# 注意: デスティネーションへの書き込みは全て失われる
aws fsx delete-s3-access-point --s3-access-point-id ${AP_ID} --region ${REGION}

curl -sk -u "fsxadmin:${FSX_PASSWORD}" \
  -X PATCH "https://${MGMT_IP}/api/snapmirror/relationships/${SM_REL_UUID}" \
  -H 'Content-Type: application/json' \
  -d '{"state": "snapmirrored"}'
```

## References

- Validation evidence: `.private/evidence/s3ap-multicloud/tc01-snapmirror-intracluster.md`
- Validation evidence: `.private/evidence/s3ap-multicloud/tc02-snapmirror-break-reattach.md`
- Research Document: `integrations/snapmirror-flexcache-multicloud/docs/ja/research.md` (SM-001〜SM-007)
