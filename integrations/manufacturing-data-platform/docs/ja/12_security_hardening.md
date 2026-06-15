# セキュリティ強化

🌐 [English](../en/12_security_hardening.md) | **日本語**

---

> SA ペルソナレビューボードの P1-#5 に対処（ペルソナ5: セキュリティレビュアー）。
> 対象: シークレット管理、明示的拒否ポリシー、監査証跡、暗号化設定。

---

## SEC-001: シークレット管理

### シークレットインベントリ

| シークレット | コンポーネント | 保存場所 | ローテーションポリシー |
|-----------|------------|---------|---------------------|
| MSK SASL/SCRAM 資格情報 | Kafka プロデューサー/コンシューマー | AWS Secrets Manager | 90 日 |
| ClickHouse 管理者パスワード | ClickHouse Cloud/オンプレ | AWS Secrets Manager | 90 日 |
| ONTAP S3 アクセスキー + シークレット | ClickHouse コールド階層、ペイロードジェネレーター | AWS Secrets Manager | 90 日 |
| Databricks サービスプリンシパルトークン | ストリーミングパイプライン、CI/CD | AWS Secrets Manager | 30 日 |
| FSx for ONTAP SVM 管理者パスワード | SVM 管理 | AWS Secrets Manager | 90 日 |
| エッジデバイス Kafka 資格情報 | Raspberry Pi プロデューサー | ローカル暗号化設定 (Phase B) | デバイスローテーション時 |

### ルール

1. ソースコード、CloudFormation パラメータ、バージョン管理の環境変数にシークレットを**絶対にハードコードしない**
2. AWS サービス間認証には **IAM ロール**を使用（静的資格情報より優先）
3. 非 IAM 資格情報は全て **Secrets Manager** に格納
4. **ローテーション自動化**: PoC では Lambda ベースのローテーション設定（または手動スケジュール）
5. **Secrets Manager アクセス**: 各コンポーネントの IAM ロールのみが自身のシークレットを読み取り可能

---

## SEC-002: 明示的拒否ポリシー

### 原則: デフォルト拒否、明示的に許可

#### MSK IAM ポリシー — プロデューサー（書き込みのみ）

- WriteData + DescribeTopic のみ Allow
- ReadData, AlterGroup, DeleteTopic, AlterTopic は明示的に Deny

#### MSK IAM ポリシー — コンシューマー（読み取りのみ）

- ReadData + DescribeTopic + AlterGroup のみ Allow
- WriteData, CreateTopic, DeleteTopic は明示的に Deny

#### FSx for ONTAP — エクスポートポリシー拒否

- エッジサブネット + ClickHouse サブネットのみ NFS アクセス許可
- その他は暗黙的拒否（マッチングルールなし = アクセス不可）

---

## SEC-003: 監査証跡設定

### 監査ログ集約戦略

| ソース | ログタイプ | 宛先 | 保持期間 |
|--------|---------|------|---------|
| CloudTrail | 管理 + データイベント | S3（暗号化、検証済み） | 90 日 (PoC)、1 年 (本番) |
| ClickHouse | query_log | ClickHouse システムテーブル | 30 日 |
| ONTAP | ファイルアクセス監査 | ONTAP 監査ボリューム | 30 日 |
| Databricks | Unity Catalog 監査 | Databricks システムテーブル | 365 日（マネージド） |
| MSK | ブローカーログ | CloudWatch Logs | 30 日 |

---

## SEC-004: 暗号化設定

### 保存時暗号化

| コンポーネント | メカニズム | キー | ステータス |
|-------------|---------|-----|---------|
| S3 (Delta テーブル) | SSE-KMS | `alias/manufacturing-poc-delta-key` | 必須 |
| FSx for ONTAP | ボリューム暗号化 | AWS 管理 KMS キー (デフォルト) | デフォルトで有効; 設定で明示 |
| ClickHouse Cloud | プロバイダー管理 | プロバイダー管理 | マネージド |
| MSK | 保存時暗号化 | AWS 管理 KMS キー | デフォルトで有効 |

### 転送時暗号化

| 接続 | メカニズム | 設定 |
|------|---------|------|
| エッジ → Kafka | SASL_SSL (TLS 1.2+) | Producer security.protocol=SASL_SSL |
| Kafka → ClickHouse | SASL_SSL or SSL (mTLS) | Kafka Engine settings |
| Kafka → Databricks | SASL_SSL | Structured Streaming options |
| クライアント → FSx NFS | NFSv4.1 + Kerberos (PoC ではオプション) | 本番では krb5p |
| クライアント → FSx ONTAP S3 | HTTPS (TLS 1.2+) | S3 エンドポイント ポート 443 |
| FlexCache インタークラスター | クラスターピアリング暗号化 | `cluster peer create -encryption true` |

---

## SEC-005: ネットワークセキュリティ

### セキュリティグループルール（最小権限）

| SG 名 | 方向 | ソース | ポート | 目的 |
|--------|------|--------|------|------|
| sg-msk | Inbound | sg-edge-producer | 9098 | Kafka IAM 認証 |
| sg-msk | Inbound | sg-clickhouse | 9098 | ClickHouse コンシューマー |
| sg-msk | Inbound | sg-databricks | 9098 | Databricks コンシューマー |
| sg-msk | Deny | 0.0.0.0/0 | All | その他全て拒否 |
| sg-fsxn | Inbound | sg-edge-producer | 2049 | NFS |
| sg-fsxn | Inbound | sg-clickhouse | 443 | ONTAP S3 |
| sg-fsxn | Inbound | sg-databricks | 2049 | NFS (FlexCache アクセス) |
| sg-fsxn | Deny | 0.0.0.0/0 | All | その他全て拒否 |

---

## ペルソナレビューノート

- **ペルソナ 5 (セキュリティ)**: 全 P1 セキュリティ指摘に対処。Secrets Manager でシークレット管理。拒否ポリシー明示。監査証跡が全コンポーネントをカバー。暗号化は保存時・転送時に強制。
- **ペルソナ 2 (ストレージ)**: ONTAP エクスポートポリシーと S3 認証チェーン文書化。ファイルアクセスの監査ログ有効化。
- **機密性**: ✅ Pass — 全 ARN はプレースホルダーアカウント ID。実 CIDR ブロックなし。実資格情報なし。
