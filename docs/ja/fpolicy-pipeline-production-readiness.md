# FPolicy 監査パイプライン — 本番運用準備ガイド

[English version](../en/fpolicy-pipeline-production-readiness.md)

> 6名のペルソナレビューサイクルに基づき作成 (2026-06-15)
> すべての技術的主張は AWS および NetApp ドキュメントで検証済み

---

## 1. ONTAP EVTX/XML フォーマット制約

### 確認済み事実

**ONTAP は 1 つの SVM で同時に EVTX と XML の両方を出力することはできない。**

出典: [NetApp KB — Can ONTAP generate CIFS audit logs in both EVTX and XML formats at the same time?](https://kb.netapp.com/on-prem/ontap/da/NAS/NAS-KBs/Can_ONTAP_generate_CIFS_audit_logs_in_both_EVTX_and_XML_formats_at_the_same_time)

### 移行影響

| 現在のフォーマット | XML 切替の影響 | 緩和策 |
|---|---|---|
| EVTX (Windows Event Viewer) | EVTX を消費する既存 SIEM 連携が停止 | デュアル SVM 戦略 or フォーマット変換レイヤー |
| XML (既に使用中) | 影響なし | — |
| 監査未構成 | 影響なし | — |

### 推奨移行戦略

```
オプション A: 専用監査 SVM
  - 新しい SVM を XML フォーマットで作成（このパイプライン用）
  - 既存 SVM は EVTX のままレガシーツール向けに維持
  - 必要に応じて SVM 間データ共有 (FlexCache) を利用

オプション B: 段階的切替
  - Phase 1: 既存 EVTX を読み取るパイプラインをデプロイ（EVTX パーサーモジュール追加）
  - Phase 2: パイプライン出力がレガシー SIEM と一致することを検証
  - Phase 3: SVM を XML に切替、レガシー EVTX コンシューマーを廃止
  - ロールバック: 問題発生時は EVTX に戻す（監査設定変更は即時反映）

オプション C: フォーマット変換レイヤー
  - SVM 上は EVTX のまま維持
  - S3 AP 読み取り後に Lambda ベースの EVTX→XML コンバーターを追加
  - トレードオフ: 追加のコンピュートコストとレイテンシ
```

---

## 2. S3 Access Point I/O オーバーヘッド

### プロビジョンドスループットへの影響

FSx for ONTAP S3 AP 読み取りはファイルシステムのプロビジョンドスループットを消費する。

**サイジング考慮事項:**
- 監査ログファイルは一般的に小さい (1-50 MB)
- 読み取りパターン: シーケンシャル、低頻度（イベント駆動）
- 典型的なスループット: 監査ログ読み取りで < 10 MB/s
- 本番 NFS/SMB ワークロードへの影響: イベント駆動パイプラインでは**無視可能**

**注意が必要なケース:**
- バックフィル（大量の履歴監査ファイルの一括読み取り）
- 高頻度ポーリング（大きなファイルに対するサブ分間隔のアクセス）
- スループット容量上限に近いファイルシステム

---

## 3. 本番チェックポイント設計 (DynamoDB)

### DynamoDB テーブルスキーマ

```
テーブル: fpolicy-pipeline-checkpoints
  PK: file_path (S)        # 監査ログファイルの S3 AP パス
  SK: segment_id (S)       # 単一ファイル処理の場合は "FULL"

属性:
  status:        S  # PENDING | PROCESSING | COMPLETED | FAILED
  lease_expiry:  N  # Unix タイムスタンプ — ロック自動解除時刻
  processor_id:  S  # Lambda リクエスト ID（呼び出しごとに一意）
  version:       N  # 楽観的ロックバージョン
  last_offset:   N  # バイトオフセットまたはイベントカウント
  ttl:           N  # DynamoDB TTL — COMPLETED レコードを7日後に自動削除
```

### ゴーストロック防止（リースタイムアウト）

```
Lambda 起動
  │
  ├── acquire_lease(file_path, request_id)
  │     │
  │     ├── [成功] → ファイル処理 → complete_processing()
  │     │
  │     └── [ConditionalCheckFailed]
  │           │
  │           └── 確認: lease_expiry < 現在時刻？
  │                 │
  │                 ├── [はい: ゴーストロック] → 新しいリースで上書き
  │                 │
  │                 └── [いいえ: アクティブ処理中] → スキップ、正常終了
  │
  └── [Lambda タイムアウト/クラッシュ]
        │
        └── lease_expiry が15分後に自動失効
              → 次の呼び出しがリースを取得可能
```

---

## 4. セキュリティ: 不変性とクロスアカウントログ集約

### S3 Object Lock（監査ログ改ざん防止）

- モード: **COMPLIANCE**（ルートユーザーでも保持期間内は削除不可）
- 保持期間: 規制要件に応じて設定（例: 365日）
- SEC 17a-4、FINRA、日本の金商法同等の規制に対応

### クロスアカウント S3 AP ポリシー

セキュリティアカウントから本番アカウントの S3 AP 経由で監査ログを読み取るための設定。

出典: [AWS ブログ — S3 Access Points でのクロスアカウントアクセス設定](https://aws.amazon.com/blogs/storage/setting-up-cross-account-amazon-s3-access-with-s3-access-points/)

---

## 5. PII マスキング（フィールドレベル戦略）

### FIELD_MAPPING 拡張（処理戦略付き）

```python
FIELD_MAPPING = {
    "timestamp": {"keys": [...], "action": "keep"},
    "user":      {"keys": [...], "action": "hash"},       # ソルト付き SHA-256
    "client_ip": {"keys": [...], "action": "mask"},       # サブネットのみ保持
    "path":      {"keys": [...], "action": "truncate_dir"}, # ディレクトリ名のみ
}
```

### ハッシュ化フィールドの運用

| 懸念 | 対策 |
|------|------|
| インシデント対応で元のユーザー名が必要 | セキュリティアカウントにルックアップテーブルを保持（暗号化、アクセス制御） |
| ソルトローテーション | 四半期ごとにローテーション、90日間のルックバック用に前回ソルトを保持 |
| 法的ホールド/フォレンジック | デュアル承認（セキュリティ + 法務）でルックアップテーブルにアクセス |

---

## 6. Splunk HEC 互換性ノート

### Indexer Acknowledgement の差異

| 挙動 | Splunk HEC (ネイティブ) | LogScale HEC 互換エンドポイント |
|------|------------------------|-------------------------------|
| HTTP 200 の意味 | インデクサーキューに受信済み | インデキシング受け入れ済み |
| Indexer Acknowledgement | ✅ サポート (`/services/collector/ack`) | ❌ 未実装 |
| データ損失保証 | ack レスポンス後: ディスク書き込み保証 | HTTP 200 後: ベストエフォート |

### SPL vs CQL クエリ比較

| ユースケース | Splunk SPL | CrowdStrike LogScale CQL |
|------------|-----------|--------------------------|
| 5分バケット | `\| bin _time span=5m \| stats count by _time` | `groupBy(_bucket=5m, function=count())` |
| Top ユーザー | `\| top limit=10 user` | `top(user, limit=10)` |
| フィルタ+集計 | `source="fpolicy" \| stats count by user` | `source="fpolicy" \| groupBy(user, function=count())` |

---

## 7. OpenTelemetry / Grafana Alloy 代替パス

### OTel を使うべき場面

| シナリオ | 推奨パス |
|---------|---------|
| SIEM 単一宛先 | Lambda → 直接 HEC |
| マルチ宛先（SIEM + メトリクス + トレース） | OTel Collector / Grafana Alloy |
| 既存 Grafana LGTM スタック | Grafana Alloy + Loki エクスポーター |
| 高カーディナリティフィールド管理 | OTel Transform Processor |

---

## 参考文献

- [NetApp KB: EVTX/XML 同時出力](https://kb.netapp.com/on-prem/ontap/da/NAS/NAS-KBs/Can_ONTAP_generate_CIFS_audit_logs_in_both_EVTX_and_XML_formats_at_the_same_time)
- [AWS: S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
- [AWS: DynamoDB 楽観的ロック](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/BestPractices_OptimisticLocking.html)
- [AWS: S3 AP クロスアカウント](https://aws.amazon.com/blogs/storage/setting-up-cross-account-amazon-s3-access-with-s3-access-points/)
- [Splunk: HEC Indexer Acknowledgement](https://help.splunk.com/en/splunk-cloud-platform/get-data-in/get-started-with-getting-data-in/10.1.2507/get-data-with-http-event-collector/about-http-event-collector-indexer-acknowledgment)
