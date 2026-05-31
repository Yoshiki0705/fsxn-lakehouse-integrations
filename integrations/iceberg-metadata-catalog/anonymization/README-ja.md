# 匿名化パイプライン (Phase 6)

🌐 日本語 | [English](README.md)

## 概要

AI エンリッチメントパイプライン (Phase 3) で `has_pii=true` とフラグされたファイルを処理し、匿名化バージョンを作成する。**データクリーンルーム**パターンを実装: オリジナルファイルは制限アクセスのまま、匿名化バージョンはより広い範囲のユーザーがアクセス可能。

## アーキテクチャ

```
S3 Tables (has_pii=true, anonymization_status='pending')
  → EventBridge スケジュール (毎時)
    → Step Functions: AnonymizationWorkflow
      → DetermineFileType
        → ドキュメント: anonymize-document Lambda (PII 墨消し)
        → 画像: anonymize-image Lambda (顔ぼかし via Rekognition)
        → DICOM: anonymize-dicom Lambda (Safe Harbor 匿名化)
      → 匿名化ファイルを S3 出力バケットに書き込み
      → メタデータ更新: anonymized_path, anonymization_status='completed'
      → "クリーン" メタデータテーブル更新 (広範囲アクセス)
```

## Lambda 関数

| 関数 | 入力 | 処理 | 出力 |
|------|------|------|------|
| `anonymize-document` | FSx S3 AP からテキスト/PDF | 正規表現 + Comprehend PII 墨消し | 墨消し済みテキスト → S3 |
| `anonymize-image` | FSx S3 AP から画像 | Rekognition 顔検出 + Pillow ぼかし | ぼかし済み画像 → S3 |

## データクリーンルームパターン

```
┌─────────────────────────────────────────────────────────┐
│ オリジナルメタデータテーブル (制限アクセス)                │
│   - PII 含むファイルを含む全ファイル                      │
│   - アクセス: METADATA_ADMIN_ROLE, COMPLIANCE_ROLE のみ   │
│   - file_path は FSx for ONTAP (オリジナル) を指す        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ クリーンメタデータテーブル (広範囲アクセス)               │
│   - anonymization_status='completed' OR has_pii=false    │
│   - アクセス: 全認可アナリスト                           │
│   - file_path は匿名化済み S3 コピーを指す               │
│   - Lake Formation: LF-Tag sensitivity != 'restricted'   │
└─────────────────────────────────────────────────────────┘
```

## 品質保証

| ステージ | 自動化 | 人間レビュー |
|---------|--------|-----------|
| PII 検出 | Comprehend + Bedrock (精度 95-98%) | — |
| 匿名化 | 正規表現 + Comprehend 墨消し / Rekognition ぼかし | — |
| 検証 | 匿名化ファイルの自動再スキャン | 週次 5% サンプル |
| エスカレーション | ミス率 > 2% → パイプライン一時停止 | コンプライアンスチームレビュー |

## コスト見積もり (1000 PII ファイル/月)

| コンポーネント | 月額コスト |
|-------------|-----------|
| Comprehend PII 検出 | ~$5 (Phase 3 で実施済み) |
| Rekognition 顔検出 | ~$10 (1000画像 × $0.01) |
| Lambda コンピュート | ~$5 |
| S3 ストレージ (匿名化コピー) | ~$2 |
| **合計** | **~$22/月** |
