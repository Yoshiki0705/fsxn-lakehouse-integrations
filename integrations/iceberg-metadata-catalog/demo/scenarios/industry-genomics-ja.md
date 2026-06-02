# ゲノミクス・バイオテック向けデモシナリオ: シーケンシングデータ & バリアント解析インテリジェンス

🌐 日本語 | [English](industry-genomics.md)

> シーケンシングレポート、FASTQ品質ログ、バリアント解析ファイル、患者同意書をゲノミクスのファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

ゲノミクス機関が直面する課題：

- **データ規模の爆発**: 各シーケンシングランが数百のファイル（FASTQ、BAM、VCF）を複雑な命名とバージョニングで生成
- **品質追跡のギャップ**: QC レポートとメトリクスがラン・ディレクトリに散在し、集約された可視性がない
- **バリアント解釈の遅延**: 関連するバリアント解析と臨床アノテーションの検索に複数プロジェクト横断が必要
- **同意管理の複雑さ**: 患者同意書とデータ利用契約が試験間で一貫性なく保管

### 解決後の姿

- シーケンシング出力がサンプル、ラン、パイプラインバージョン、品質ステータス別に自動分類
- 「先月のパネルシーケンシングで QC 失敗したランをすべて表示」が SQL で即座に回答
- バリアント解析ファイルがサンプルに紐づき臨床的意義のアノテーション付き
- 同意書が有効期限と許可されたデータ利用範囲で追跡

---

## デモフロー

### ステップ 1: サンプルゲノミクスファイルを FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry genomics --target /vol/genomics-data/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `qc-report-RUN2026042-S001.html` | QC レポート | シーケンシング品質メトリクス、サンプル S001 |
| `variant-call-S001-germline.vcf` | バリアントファイル | 生殖細胞系バリアントコール、42,847 バリアント |
| `fastq-metrics-RUN2026042.json` | FASTQ メトリクス | ランレベルの品質統計 |
| `consent-form-PT8842-genomic-v2.pdf` | 同意書 | 患者ゲノムデータ同意書、v2 |
| `clinical-annotation-S001-pathogenic.tsv` | 臨床アノテーション | 病原性バリアントアノテーション |

**トークポイント**:
- 「FSx の高スループット NFS がバイオインフォマティクスパイプラインの I/O 要求に対応」
- 「FPolicy はパイプライン出力ファイルで計算性能に影響なくトリガー」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: qc-report-RUN2026042-S001.html
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: QC レポート/シーケンシング
   - ラン ID: RUN2026042
   - サンプル ID: S001
   - シーケンシングタイプ: WGS（全ゲノム）
   - カバレッジ: 30x 平均
   - 品質: PASS（Q30 > 85%）
   - パイプライン: GATK 4.5.2
   - 機器: NovaSeq 6000
✅ Classified in 39.8s | Cost: $0.07
```

**トークポイント**:
- 「AI がシーケンシングタイプ、品質メトリクス、パイプラインバージョン、合否ステータスを識別」
- 「バリアントファイルがタイプ（生殖細胞系、体細胞）と臨床的意義で分類」
- 「分類信頼度: PoC 精度。本番精度はレポート形式により変動」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       run_id, sample_id, sequencing_type, quality_status
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'genomics'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | run_id | sample_id | quality_status |
|-----------|------------------|:---------:|:------:|:---------:|:--------------:|
| /vol/genomics-data/qc-report-RUN2026042-S001.html | QCレポート/シーケンシング | 0.96 | RUN2026042 | S001 | PASS |
| /vol/genomics-data/variant-call-S001-germline.vcf | バリアント/生殖細胞系 | 0.95 | RUN2026042 | S001 | - |
| /vol/genomics-data/fastq-metrics-RUN2026042.json | FASTQメトリクス | 0.98 | RUN2026042 | - | PASS |
| /vol/genomics-data/consent-form-PT8842-genomic-v2.pdf | 同意書/ゲノム | 0.94 | - | S001 | - |
| /vol/genomics-data/clinical-annotation-S001-pathogenic.tsv | 臨床アノテーション | 0.93 | - | S001 | - |

**トークポイント**:
- 「ランとサンプルの紐づけがファイルタイプ間で自動維持」
- 「品質合否ステータスが抽出されパイプラインモニタリングに活用」
- 「同意書が患者/サンプルに紐づきデータガバナンスに対応」

---

### ステップ 4: ゲノミクス向けクエリ

**所要時間**: 5 分

```sql
-- 過去30日間のQC失敗ラン
SELECT run_id, sample_id, quality_status, failure_reason, run_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'QCレポート/シーケンシング'
  AND quality_status = 'FAIL'
  AND scan_timestamp > current_date - interval '30' day
ORDER BY run_date DESC;

-- 臨床レビューが必要な病原性バリアントのサンプル
SELECT sample_id, file_path, pathogenic_count, gene_list
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = '臨床アノテーション'
  AND pathogenic_count > 0
ORDER BY pathogenic_count DESC;

-- 同意書の有効期限追跡
SELECT patient_id, sample_id, consent_scope, expiry_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = '同意書/ゲノム'
  AND expiry_date < current_date + interval '180' day
ORDER BY expiry_date ASC;
```

**トークポイント**:
- 「ラボディレクターが QC トレンドを監視し系統的な問題を特定」
- 「臨床遺伝専門医がアクショナブルな所見のサンプルを優先」
- 「データガバナンスチームが同意カバレッジと有効期限を追跡」

---

### ステップ 5: バリアント発見のためのセマンティック検索

**所要時間**: 5 分

**シナリオ**: 「コホート分析のために類似バリアントプロファイルのサンプルを検索」

OpenSearch を使用：
1. **キーワード検索**: `"BRCA1" AND "pathogenic"` → 正確なバリアント一致
2. **セマンティック検索**: 「DNA修復経路遺伝子における乳がん素因バリアント」→ 関連アノテーションを発見
3. **組み合わせ**: バリアント意義 + 遺伝子パスウェイ + セマンティック類似度フィルター

**トークポイント**:
- 「研究コホートの特定が数日から数分に加速」
- 「異なるアノテーション標準間でもセマンティック検索が関連バリアントを発見」
- 「OpenSearch Serverless の注意点: 長時間アイドル後の最初の検索は OCU ウォームアップに 10–30 秒」

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 94% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 40 秒/ファイル | メタデータ抽出。バリアントコーリングではない |
| 1 ファイルあたりコスト | $0.05–$0.07 | レポートファイル。大容量BAM/FASTQはメタデータのみ |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| QC モニタリング | 30 分/日 × 5 ラボ技術者 → 自動化ダッシュボード | **~45 時間/年** |
| サンプル追跡 | 15 分/サンプル × 2,000 サンプル/年 → 2 分 | **433 時間削減** |
| 同意コンプライアンス | 4 時間/週の手動追跡 → 自動化 | **192 時間削減** |
| バリアントコホート検索 | 2 日/検索 × 50 検索/年 → 30 分 | **775 時間削減** |

**保守的年間生産性効果**: ~1,445 時間 × ¥7,000/時 = **¥10,115,000**（~$67,400）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~4,793%

**前提条件**: 50% 利用率、中規模ゲノミクスラボ、発見の加速や臨床ターンアラウンド改善の追加価値は含まず。

---

## ゲノミクスに関連する制限事項

| 制限事項 | ゲノミクスへの影響 |
|---------|-----------------|
| S3 AP 読み取り専用 | カタログ経由で再解析パイプラインをトリガー不可 |
| S3 Event Notifications 非対応 | S3 イベント経由の下流分析トリガー不可 |
| 大容量バイナリファイル | BAM/CRAM ファイル（10–100GB）はメタデータのみ処理。コンテンツレベル分析なし |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| 臨床解釈 | AI 分類はメタデータレベル。臨床的バリアント解釈ではない |
| 同意の機微性 | 患者データ取り扱いは施設の倫理委員会要件に準拠必須 |
| データ主権 | ゲノムデータに国固有の保管要件がある場合あり（例: 日本の APPI） |

---

## カスタマイズポイント

1. **パイプラインバージョン**: 複数のバイオインフォマティクスパイプライン追跡（GATK、DRAGEN、カスタム）
2. **パネルタイプ**: WGS、WES、ターゲットパネル、RNA-seq 等を設定
3. **バリアントデータベース**: ClinVar、COSMIC、gnomAD バージョンへのアノテーションリンク
4. **同意スコープ**: 施設ポリシーに基づく許可されたデータ利用カテゴリを定義

---

## Iceberg Time Travel: 履歴比較

Iceberg テーブル形式のユニークな利点の一つがタイムトラベル — 過去の任意の時点でのメタデータをクエリする機能です。

```sql
-- スナップショット履歴の表示
SELECT * FROM s3_tables.metadata_catalog.file_metadata$snapshots
ORDER BY committed_at DESC LIMIT 10;

-- 24 時間前の時点でのメタデータをクエリ
SELECT ai_classification, COUNT(*) as file_count
FROM s3_tables.metadata_catalog.file_metadata
FOR TIMESTAMP AS OF (current_timestamp - interval '24' hour)
GROUP BY ai_classification;

-- 現在 vs. 以前の分類件数を比較
WITH current_state AS (
  SELECT ai_classification, COUNT(*) as current_count
  FROM s3_tables.metadata_catalog.file_metadata
  GROUP BY ai_classification
),
previous_state AS (
  SELECT ai_classification, COUNT(*) as previous_count
  FROM s3_tables.metadata_catalog.file_metadata
  FOR TIMESTAMP AS OF (current_timestamp - interval '7' day)
  GROUP BY ai_classification
)
SELECT COALESCE(c.ai_classification, p.ai_classification) as category,
       COALESCE(c.current_count, 0) as now,
       COALESCE(p.previous_count, 0) as week_ago,
       COALESCE(c.current_count, 0) - COALESCE(p.previous_count, 0) as delta
FROM current_state c
FULL OUTER JOIN previous_state p ON c.ai_classification = p.ai_classification
ORDER BY delta DESC;
```

**この業界でのタイムトラベル活用例**:
- ファイル分類分布の時系列変化を追跡
- コンプライアンス判断時のメタデータ状態を監査
- 意図しない一括再分類や削除からの復旧
- 異なる AI モデルバージョン間のエンリッチメント結果比較


---

*関連: [use-cases/genomics/](../../use-cases/genomics/)*
*ペアドキュメント: [industry-genomics.md](./industry-genomics.md)*
