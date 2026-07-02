# Iceberg メタデータ採用検証チェックリスト

🌐 [English](iceberg-adoption-validation-checklist.md) | 日本語

## 目的

- Iceberg がここで解決するビジネス課題は？ → 生ファイルコピーなしでの非構造化データ発見、ガバナンス、AI レディネス
- なぜ生ファイル移行ではなくメタデータのみか？ → 生ファイルは FSx for ONTAP に残る（NFS/SMB/S3 AP アクセス維持）; 構造化メタデータのみをカタログ化

## スコープ

| カテゴリ | スコープ内 | スコープ外 |
|---------|----------|----------|
| 生データ | FSx for ONTAP ファイル（S3 AP 経由で読み取り） | ファイルは S3 に移行しない |
| メタデータ | S3 Tables Iceberg のファイルインベントリ + AI エンリッチメント | 生ファイルコンテンツの保存 |
| コンシューマー | Athena, EMR Spark, Snowflake, Databricks（アクティベーション経由） | Snowflake/Databricks での直接ファイル処理 |
| スコープ外パス | — | FSx for ONTAP S3 AP への Iceberg 書き込み、Databricks UC 直接 S3 Tables アクセス |

## 検証チェックリスト

### データ完全性
- [ ] scan_run_id ごとの行数が期待ファイル数と一致
- [ ] file_id / path_hash による重複検出（比率 < 2x）
- [ ] Latest-record ビューの正確性（ユニークファイル数と一致）
- [ ] 削除マーカー動作（is_deleted ファイルが latest ビューから除外）
- [ ] 全ターゲットボリューム/プレフィックスがスキャン済み

### Iceberg 動作
- [ ] スナップショット / タイムトラベル動作を確認
- [ ] S3 Tables 自動コンパクションを観察
- [ ] Append-only 書き込みセマンティクスを理解
- [ ] 命名規則（小文字）を適用

### クロスプラットフォーム互換性
- [ ] Athena クエリ互換性（SELECT, COUNT, タイムトラベル）
- [ ] EMR Spark 互換性（7.13.0+ 必須）
- [ ] Snowflake 互換性（VENDED_CREDENTIALS, AUTO_REFRESH, タイムトラベル）
- [ ] Databricks 互換性ステータスを文書化（2026-06-09 再テスト: 依然ブロック）

### コスト
- [ ] メタデータストレージコスト（S3 Tables）
- [ ] スキャン/エンリッチメント計算コスト（Lambda/ECS）
- [ ] AI エンリッチメントコスト（Bedrock）
- [ ] クエリコスト（Athena/Snowflake ウェアハウス）
- [ ] 検索インデックスコスト（OpenSearch）
- [ ] バックフィル vs 定常状態コストを分離

### コンシューマーアクティベーション
- [ ] Athena named queries 作成
- [ ] BI ビュー（latest-record、PII カバレッジ）公開
- [ ] Snowflake アクティベーション（VENDED_CREDENTIALS またはメタデータ同期）
- [ ] Databricks アクティベーション（UC Delta へのメタデータ同期または Foreign Iceberg 利用可能時）

## 参考

- [本番化成熟度モデル](../genai/production-maturity-model-ja.md)
- [PoC 結果サマリー](poc-results-summary-ja.md)
- [コスト前提条件](../verification-evidence/cost-assumptions.yaml)
