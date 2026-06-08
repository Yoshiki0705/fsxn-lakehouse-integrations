# Apache Iceberg 仕様 vs AWS S3 Tables サービス動作

🌐 [English](standards-vs-service-behavior.md) | 日本語

## 目的

オープンな Apache Iceberg 仕様と AWS S3 Tables サービス固有の動作の境界を明確にする。Iceberg 仕様の全機能が S3 Tables で利用可能、または同一の挙動であると仮定してはならない。

## 比較

| 領域 | Apache Iceberg 仕様 | AWS S3 Tables 動作 |
|------|--------------------|--------------------|
| **テーブルフォーマット** | オープン仕様 (format-version 1 および 2) | マネージド Iceberg テーブルバケット (format-version 2) |
| **カタログ API** | REST Catalog 仕様 (オープン) | S3 Tables REST エンドポイント + AWS Glue Iceberg REST エンドポイント |
| **ガバナンス** | Iceberg 仕様では未定義 | IAM + Lake Formation (AWS 固有) |
| **テーブルメンテナンス** | エンジン/カタログ依存 (Spark, Trino 等) | S3 Tables サービスマネージド自動コンパクション |
| **スナップショット有効期限** | エンジンで明示実行 (例: Spark `expire_snapshots`) | S3 Tables サービスマネージドポリシーを確認 |
| **マニフェスト書き換え** | エンジンで明示実行 | S3 Tables 自動コンパクションのスコープを確認 |
| **孤立ファイルクリーンアップ** | エンジンで明示実行 | サービス責任範囲を確認 |
| **主キー / 一意性** | Iceberg では強制しない | 強制しない — dedup ビューを使用 |
| **行レベル削除** | Position Delete Files (v2) | PyIceberg ソフトデリートレコードの append でサポート |
| **スキーマ進化** | 仕様でサポート | PyIceberg / Glue 経由でサポート |
| **パーティション進化** | 仕様でサポート | S3 Tables + Athena で検証すること |
| **タイムトラベル** | 仕様でサポート (スナップショットベース) | Athena `$history` / `FOR TIMESTAMP AS OF` + Snowflake `AT(OFFSET)` で検証済み |
| **命名規則** | 仕様は大文字小文字混在を許可 | S3 Tables は AWS 分析サービス統合に小文字を要求 |

## 本プロジェクトへの影響

1. **メンテナンス**: Spark スタイルの `expire_snapshots` や `rewrite_manifests` が S3 Tables で動作すると仮定できない。サービスマネージド動作を確認すること。
2. **ガバナンス**: Lake Formation 統合は AWS 固有であり、Iceberg 仕様の一部ではない。
3. **命名規則**: 小文字要件は S3 Tables / Glue / Athena の制約であり、Iceberg 仕様の要件ではない。
4. **重複排除**: Iceberg は一意性を強制しない — `latest_records.sql` ビューがクエリ時に対応する。

## 参考

- [Apache Iceberg 仕様](https://iceberg.apache.org/spec/)
- [Iceberg REST Catalog 仕様](https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml)
- [S3 Tables ドキュメント](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables.html)
- [AWS Glue Iceberg REST エンドポイント](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-glue-endpoint.html)
