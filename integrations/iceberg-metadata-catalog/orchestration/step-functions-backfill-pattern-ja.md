# Step Functions Distributed Map — バックフィルパターン

🌐 [English](step-functions-backfill-pattern.md) | 日本語

## 目的

大規模な初期バックフィル（10 万ファイル以上）において、Step Functions Distributed Map を使用して並行処理を並行度制御、失敗閾値、進捗追跡付きでオーケストレーションする。

## 使用するタイミング

| シナリオ | 推奨オーケストレーション |
|---------|----------------------|
| 日次増分（1000 ファイル未満） | SQS → Lambda（既存パイプライン） |
| 初期バックフィル（1 万〜100 万ファイル） | **Step Functions Distributed Map** |
| モデル変更後の再エンリッチメント | Step Functions Distributed Map |
| OpenSearch リインデックス | Step Functions Distributed Map |

## アーキテクチャ

```
Step Functions (Distributed Map)
  │
  ├── 入力: 処理対象ファイルの S3 マニフェスト
  │
  ├── Map ステート（最大 10,000 並列子実行）
  │   ├── 子 1: ファイルエンリッチ → S3 Tables に書き込み
  │   ├── 子 2: ファイルエンリッチ → S3 Tables に書き込み
  │   └── ...
  │
  ├── 失敗閾値: 最大 10% の失敗を許容
  │
  └── 出力: サマリー（処理済み、失敗、スキップ）
```

## 主要設定

- `MaxConcurrency`: 10 から開始し、FSx スループットへの影響を検証後に増加
- `ToleratedFailurePercentage`: 10%（完了後に失敗を調査）
- `ItemReader`: S3 マニフェスト JSON（処理対象ファイルパスのリスト）
- 子ワークフロー: Lambda 関数（増分処理と同じエンリッチメントロジック）

## SQS のみと比較した利点

- **進捗の可視性**: 処理済み/残りのファイル数を正確に把握
- **失敗閾値**: 失敗が多すぎる場合に早期停止（不良モデル、権限問題）
- **一時停止/再開**: 進捗を失わずに停止・再開が可能
- **並行度制御**: 明示的な最大並列度（FSx スループットを保護）
- **コスト**: ステート遷移ごとの課金であり、アイドル Lambda ごとではない

## 参考資料

- [Step Functions Distributed Map](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-asl-use-map-state-distributed.html)
