# 小売・流通業向けデモシナリオ: 商品カタログ & サプライチェーン文書インテリジェンス

🌐 日本語 | [English](industry-retail.md)

> 商品画像、POS データ、サプライヤー契約書、プラノグラムをリテール部門のファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

小売業が直面する課題：

- **商品コンテンツの散在**: 商品画像、プラノグラム、マーケティング素材、サプライヤー契約書が地域別ファイル共有に散在し、統一カタログがない
- **サプライヤー文書の混乱**: 数千件の契約書、請求書、コンプライアンス証明書がバイヤーチームごとに異なる方法で保管
- **シーズン計画の遅延**: 昨年のプラノグラムやプロモーション素材を見つけるためにフォルダ階層を手動検索する必要がある
- **コンプライアンスの欠落**: サプライヤー認証や食品安全書類の有効期限が追跡されていない

### 解決後の姿

- 商品画像や文書がアップロード時に自動でカテゴリ・シーズン・ブランド別に分類
- 「有効期限切れのサプライヤー認証をすべて表示」が SQL で即座に回答
- プラノグラムのバージョン履歴やシーズン素材の検索が即座に実行可能
- サプライヤーコンプライアンス管理がデータドリブンに（自動期限アラート付き）

---

## デモフロー

### ステップ 1: サンプルリテール文書を FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry retail --target /vol/retail-ops/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `planogram-electronics-2026Q2-v3.pdf` | プラノグラム | 家電フロアレイアウト、第3版 |
| `product-image-SKU88421-front.jpg` | 商品画像 | SKU 88421 正面商品写真 |
| `supplier-contract-VND-2026-0187.pdf` | サプライヤー契約書 | 生鮮食品サプライヤー契約 |
| `pos-daily-export-20260601.csv` | POS エクスポート | 日次取引集計、12,400 件 |
| `food-safety-cert-VND0187-2026.pdf` | コンプライアンス証明書 | サプライヤー食品安全認証 |

**トークポイント**:
- 「店舗運営チームはファイルの保存方法を変える必要がありません。パイプラインは自動トリガーされます」
- 「本社の NFS 共有でも店舗レベルの SMB マウントでも動作します」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: planogram-electronics-2026Q2-v3.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: プラノグラム/フロアレイアウト
   - 部門: 家電
   - シーズン: Q2 2026
   - バージョン: 3
   - 店舗フォーマット: 標準（1,200 sqm）
   - コンプライアンス: アクセシビリティ確認済
✅ Classified in 43.2s | Cost: $0.07
```

**トークポイント**:
- 「AI が文書タイプ、部門、シーズン、バージョンを自動識別します」
- 「商品画像はカテゴリ、ブランドポジション、品質が分析されます」
- 「分類信頼度: PoC 精度。本番精度は画像品質と文書フォーマットにより変動」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
-- Athena で分類結果を確認
SELECT file_path, ai_classification, confidence_score,
       department, season, document_version
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'retail'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | department | season | version |
|-----------|------------------|:---------:|:----------:|:------:|:-------:|
| /vol/retail-ops/planogram-electronics-2026Q2-v3.pdf | プラノグラム/フロアレイアウト | 0.95 | 家電 | Q2-2026 | 3 |
| /vol/retail-ops/product-image-SKU88421-front.jpg | 商品画像/正面 | 0.93 | 家電 | - | - |
| /vol/retail-ops/supplier-contract-VND-2026-0187.pdf | サプライヤー契約書 | 0.94 | 調達 | - | - |
| /vol/retail-ops/pos-daily-export-20260601.csv | POS データエクスポート | 0.97 | 販売 | 2026-06-01 | - |
| /vol/retail-ops/food-safety-cert-VND0187-2026.pdf | コンプライアンス証明書 | 0.96 | 調達 | 2026 | - |

**トークポイント**:
- 「5種類の文書が高精度で正確に分類されました」
- 「シーズンと部門が自動抽出され、フィルタリングに使用可能」
- 「サプライヤーのコンプライアンス証明書は有効期限が追跡されます」

---

### ステップ 4: リテール業務クエリ

**所要時間**: 5 分

```sql
-- 来シーズンのプラノグラムを検索
SELECT file_path, department, document_version, last_modified
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'プラノグラム/フロアレイアウト'
  AND season = 'Q2-2026'
ORDER BY department, document_version DESC;

-- 有効期限切れのサプライヤー認証
SELECT file_path, supplier_id, certification_type, expiry_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'コンプライアンス証明書'
  AND expiry_date < current_date
ORDER BY expiry_date ASC;

-- アクティブ SKU で画像が不足しているもの
SELECT sku_id, COUNT(*) as image_count
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE '商品画像%'
GROUP BY sku_id
HAVING COUNT(*) < 3;
```

**トークポイント**:
- 「MD チームが最新バージョンのプラノグラムを即座に検索可能」
- 「調達部門がサプライヤー認証の期限切れを自動検知」
- 「EC チームが商品写真が不足している SKU を特定」

---

### ステップ 5: シーズン計画のためのセマンティック検索

**所要時間**: 5 分

**シナリオ**: 「昨年のホリデーシーズンのプロモーション素材をすべて検索」

OpenSearch を使用：
1. **キーワード検索**: `"ホリデー 2025" OR "クリスマス プロモーション"` → 完全一致
2. **セマンティック検索**: 「冬季シーズン 家電 ディスプレイレイアウト」→ 関連するプラノグラムと素材を発見
3. **組み合わせ**: 部門 + シーズン + セマンティック関連度フィルター

**トークポイント**:
- 「シーズン計画で昨年のフォルダパスを覚えている必要がなくなります」
- 「ベクトル検索が異なる命名規則でも関連素材を発見します」
- 「OpenSearch Serverless の注意点: 長時間アイドル後の最初の検索は OCU ウォームアップに 10–30 秒」

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 90% 以上（6 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 42 秒/ファイル | 単一ファイル。バッチは並行度に依存 |
| 1 ファイルあたりコスト | $0.07 | テキスト文書。商品画像: ~$0.05 |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| プラノグラム検索時間 | 15 分/検索 × 200 検索/年 | **50 時間削減** |
| サプライヤーコンプライアンス追跡 | 2 日/四半期の手動確認 → 自動化 | **64 時間削減** |
| 商品画像検索 | 5 分/日 × 30 人 MD 担当 × 50% 利用率 | **~275 時間/年** |
| シーズン素材の再利用 | 3 日/シーズンの検索 → 30 分 × 4 シーズン | **90 時間削減** |

**保守的年間生産性効果**: ~479 時間 × ¥4,000/時 = **¥1,916,000**（~$12,800）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~836%

**前提条件**: 50% ユーザー利用率、保守的な時間削減見積もり、欠品削減やプラノグラムコンプライアンス改善の追加価値は含まず。

---

## 小売業に関連する制限事項

| 制限事項 | 小売業への影響 |
|---------|--------------|
| S3 AP 読み取り専用 | パイプライン経由で古いプラノグラムや期限切れ素材を自動アーカイブ不可 |
| S3 Event Notifications 非対応 | S3 イベント経由の在庫ワークフロートリガー不可 |
| Bedrock 精度の変動 | 商品画像の分類精度は画像品質と照明条件に依存 |
| FPolicy レイテンシ (~1–5ms) | 文書管理には影響なし。POS オペレーションへの影響なし |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| 画像ファイルサイズ | 大容量商品写真（>20MB）は処理時間増加の可能性 |

---

## カスタマイズポイント

1. **分類カテゴリ**: 小売企業固有のタイプ追加（ロイヤルティプログラム素材、フォーマット別店舗レイアウト）
2. **SKU マッピング**: 商品画像を SKU マスターデータに紐づけ、網羅性追跡
3. **シーズンタグ**: 小売企業のマーチャンダイジングカレンダーに合わせたシーズン定義
4. **サプライヤーティア**: サプライヤーリスクティア別の認証要件マッピング

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

*関連: [use-cases/retail/](../../use-cases/retail/)*
*ペアドキュメント: [industry-retail.md](./industry-retail.md)*
