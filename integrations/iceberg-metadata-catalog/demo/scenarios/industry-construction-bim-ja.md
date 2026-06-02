# 建設・BIM 向けデモシナリオ: BIM モデル & 現場点検インテリジェンス

🌐 日本語 | [English](industry-construction-bim.md)

> BIM モデル、現場写真、安全点検レポート、許認可文書を建設プロジェクトのファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

建設会社が直面する課題：

- **BIM モデルバージョンの混乱**: 複数の分野（構造、MEP、建築）の IFC/RVT モデルが統一バージョン追跡なく複数リビジョン存在
- **現場文書の散在**: 日次進捗写真、安全点検レポート、RFI がプロジェクトフォルダに分散
- **許認可追跡の欠落**: 建築許可、環境承認、自治体申請が有効期限追跡なく保管
- **分野間調整**: 建築、構造、MEP の各分野の関連文書検索に手動作業が必要

### 解決後の姿

- BIM モデルと建設文書が分野、フェーズ、リビジョンステータス別に自動分類
- 「ビルAの未回答構造RFIをすべて表示」が SQL で即座に回答
- 現場写真に位置、進捗段階、安全コンプライアンスステータスのタグ付け
- 許認可の有効期限が自動期限認識で追跡

---

## デモフロー

### ステップ 1: サンプル建設ファイルを FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry construction-bim --target /vol/construction/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `model-BLDG-A-structural-rev08.ifc` | BIM モデル | 構造モデル、リビジョン8 |
| `site-photo-BLDG-A-floor3-20260601.jpg` | 現場写真 | 3階進捗、コンクリート打設 |
| `safety-inspection-BLDG-A-20260601.pdf` | 安全点検 | 日次安全点検、指摘2件 |
| `permit-building-BLDG-A-2026-renewal.pdf` | 許認可文書 | 建築許可更新 |
| `rfi-STR-042-column-spacing.pdf` | RFI 文書 | 構造柱間隔の照会 |

**トークポイント**:
- 「プロジェクトチームは CDE（共通データ環境）ワークフローを継続 — FPolicy がプロセスを変えずにインテリジェンスを追加」
- 「BIM モデルと紙スキャン文書の両方をサポート」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: model-BLDG-A-structural-rev08.ifc
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: BIM モデル/構造
   - プロジェクト: ビルA
   - 分野: 構造
   - リビジョン: 8
   - LOD: 350
   - フェーズ: 施工
   - 干渉ステータス: 3件未解決
   - フォーマット: IFC 4.0
✅ Classified in 40.2s | Cost: $0.07
```

**トークポイント**:
- 「AI がモデルメタデータから分野、リビジョン、LOD レベル、プロジェクトフェーズを識別」
- 「現場写真は進捗段階と安全コンプライアンス指標が分析」
- 「分類信頼度: PoC 精度。本番精度はファイル形式とメタデータ完全性により変動」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       project, discipline, revision, phase
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'construction-bim'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | project | discipline | revision |
|-----------|------------------|:---------:|:-------:|:----------:|:--------:|
| /vol/construction/model-BLDG-A-structural-rev08.ifc | BIMモデル/構造 | 0.95 | ビルA | 構造 | 8 |
| /vol/construction/site-photo-BLDG-A-floor3-20260601.jpg | 現場写真/進捗 | 0.92 | ビルA | - | - |
| /vol/construction/safety-inspection-BLDG-A-20260601.pdf | 安全点検 | 0.96 | ビルA | - | - |
| /vol/construction/permit-building-BLDG-A-2026-renewal.pdf | 許認可/建築 | 0.97 | ビルA | - | - |
| /vol/construction/rfi-STR-042-column-spacing.pdf | RFI/構造 | 0.94 | ビルA | 構造 | - |

---

### ステップ 4: 建設業務クエリ

**所要時間**: 5 分

```sql
-- 分野別最新BIMモデルリビジョン
SELECT project, discipline, MAX(revision) as latest_rev, file_path
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'BIMモデル%'
GROUP BY project, discipline;

-- 対応が必要なオープン安全指摘事項
SELECT file_path, project, finding_type, severity, action_due_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = '安全点検'
  AND finding_status = 'オープン'
ORDER BY severity DESC, action_due_date ASC;

-- 有効期限が近づいている許認可
SELECT file_path, project, permit_type, expiry_date, days_until_expiry
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE '許認可%'
  AND expiry_date < current_date + interval '90' day
ORDER BY expiry_date ASC;
```

---

### ステップ 5: 分野間調整のためのセマンティック検索

**所要時間**: 5 分

**シナリオ**: 「ビルA構造柱に関連するすべての文書を検索」

OpenSearch を使用：
1. **キーワード検索**: `"ビルA" AND "柱" AND "構造"` → 完全一致
2. **セマンティック検索**: 「耐力柱設計変更のMEP配管ルーティングへの影響」→ 分野間影響を発見
3. **組み合わせ**: プロジェクト + 分野 + セマンティック関連度フィルター

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 93% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 40 秒/ファイル | モデルヘッダーからのメタデータ抽出 |
| 1 ファイルあたりコスト | $0.05–$0.07 | 文書ファイル。BIM モデルはメタデータのみ |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| モデルバージョン検索 | 15 分/検索 × 300 検索/年 → 2 分 | **65 時間削減** |
| RFI 追跡 | 20 分/RFI × 200 RFI/年 → 自動化 | **57 時間削減** |
| 安全レポート検索 | 10 分/日 × 50 プロジェクト日 → 2 分 | **7 時間/プロジェクト** |
| 許認可コンプライアンス | 4 時間/月の手動追跡 → 自動化 | **44 時間削減** |

**保守的年間生産性効果**: ~173 時間 × ¥5,000/時 = **¥865,000**（~$5,800）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~324%（プロジェクト単位、ポートフォリオ規模で拡大）

---

## 建設業に関連する制限事項

| 制限事項 | 建設業への影響 |
|---------|--------------|
| S3 AP 読み取り専用 | パイプライン経由で BIM ワークフロー遷移をトリガー不可 |
| 大容量 BIM ファイル | IFC/RVT ファイル（100MB以上）はメタデータレベルで処理 |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| CDE 連携 | 専用の共通データ環境プラットフォームの補完であり代替ではない |
| ISO 19650 | AI メタデータは補完的。正式な情報管理プロセスの代替ではない |

---

## カスタマイズポイント

1. **分野マッピング**: プロジェクト固有の分野コード設定（S、A、M、E、P）
2. **LOD レベル**: プロジェクトフェーズ要件ごとの LOD 追跡
3. **安全カテゴリ**: 指摘タイプを企業の安全分類システムにマッピング
4. **許認可タイプ**: 管轄地域とプロジェクトタイプに応じて設定

---

*関連: [use-cases/construction-bim/](../../use-cases/construction-bim/)*
*ペアドキュメント: [industry-construction-bim.md](./industry-construction-bim.md)*
