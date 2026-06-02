# SAP/ERP 連携向けデモシナリオ: 請求書 & 発注書インテリジェンス

🌐 日本語 | [English](industry-sap-erp.md)

> ERPシステムデータを補完する請求書スキャン、発注書、納品書、入庫伝票の自動分類・検索デモシナリオ。

---

## ビジネスコンテキスト

### 課題

SAP/ERPシステムを持つ組織が直面する課題：

- **紙-デジタルギャップ**: 物理的な請求書、発注書、納品書がスキャンされファイル共有にERPリンケージなく保管
- **三者照合の遅延**: 請求書とPO、納品受領書の照合に複数システム横断の手動文書検索が必要
- **アーカイブ検索の困難**: 過去文書がメタデータなくアーカイブファイル共有に保管され効率的検索不可
- **監査証跡のギャップ**: ERP取引で参照される裏付け文書が非連結のファイルリポジトリに存在

### 解決後の姿

- スキャンされたERP文書がタイプ、ベンダー、PO番号、金額別に自動分類
- 「先月の100万円超の未照合請求書をすべて表示」が SQL で即座に回答
- 請求書スキャンをPO番号と納品受領書にリンクし三者照合を加速
- 文書-取引リンケージによる監査準備の簡素化

---

## デモフロー

### ステップ 1: サンプルERP文書を FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry sap-erp --target /vol/erp-docs/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `invoice-scan-VND0042-INV2026-08842.pdf` | 請求書スキャン | ベンダー請求書、¥240万、原材料 |
| `purchase-order-PO2026-04421.pdf` | 発注書 | 製造部品のPO |
| `delivery-note-DN2026-08842-partial.pdf` | 納品書 | 分納、PO数量の80% |
| `warehouse-receipt-WR2026-08842.pdf` | 入庫伝票 | 検収確認 |
| `credit-memo-CM2026-0042-return.pdf` | クレジットメモ | 返品クレジット |

**トークポイント**:
- 「メール室や荷受場でスキャンされた文書がファイル到着時に分類をトリガー」
- 「SAP ArchiveLinkやOpenTextと並行動作 — AIインテリジェンスを上乗せ」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: invoice-scan-VND0042-INV2026-08842.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: 請求書
   - ベンダー ID: VND-0042
   - 請求書番号: INV2026-08842
   - 金額: ¥2,400,000
   - PO参照: PO2026-04421
   - 日付: 2026-06-01
   - カテゴリ: 原材料
   - 消費税: ¥240,000（10%）
   - 支払条件: 60日ネット
✅ Classified in 43.8s | Cost: $0.07
```

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       vendor_id, document_number, amount, po_reference
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'sap-erp'
ORDER BY scan_timestamp DESC;
```

---

### ステップ 4: ERP業務クエリ

**所要時間**: 5 分

```sql
-- 未照合請求書（対応する納品書なし）
SELECT i.vendor_id, i.document_number, i.amount, i.po_reference
FROM s3_tables.metadata_catalog.file_metadata i
WHERE i.ai_classification = '請求書'
  AND NOT EXISTS (
    SELECT 1 FROM s3_tables.metadata_catalog.file_metadata d
    WHERE d.ai_classification = '納品書'
    AND d.po_reference = i.po_reference
  );

-- 三者照合待ちの高額請求書
SELECT file_path, vendor_id, amount, po_reference, match_status
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = '請求書'
  AND amount > 1000000
  AND match_status = '照合待ち'
ORDER BY amount DESC;

-- ベンダー別文書完備状況
SELECT vendor_id,
       COUNT(CASE WHEN ai_classification = '請求書' THEN 1 END) as invoices,
       COUNT(CASE WHEN ai_classification = '発注書' THEN 1 END) as pos,
       COUNT(CASE WHEN ai_classification = '納品書' THEN 1 END) as deliveries
FROM s3_tables.metadata_catalog.file_metadata
GROUP BY vendor_id;
```

---

### ステップ 5: 監査支援のためのセマンティック検索

**所要時間**: 5 分

**シナリオ**: 「監査のためにPO2026-04421関連の全文書を検索」

OpenSearch を使用：
1. **キーワード検索**: `"PO2026-04421"` → このPOに言及する全文書
2. **セマンティック検索**: 「2026年上半期のベンダー0042からの原材料調達」→ 関連取引を発見
3. **組み合わせ**: ベンダー + 日付範囲 + 文書タイプフィルター

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 95% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 43 秒/ファイル | OCR 品質が精度に影響 |
| 1 ファイルあたりコスト | $0.07 | スキャン文書 |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| 三者照合 | 15 分/請求書 × 5,000 件/年 → 3 分 | **1,000 時間削減** |
| 監査文書組み立て | 3 日/監査 → 4 時間 × 2 監査/年 | **40 時間削減** |
| 請求書紛争解決 | 30 分/紛争 × 200 件/年 → 5 分 | **83 時間削減** |
| 重複請求書検出 | 5 件/月 × 平均 ¥20 万 | **¥1,200 万の損失防止** |

**保守的年間生産性効果**: ~1,123 時間 × ¥4,000/時 = **¥4,492,000**（~$30,000）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~2,184%

---

## SAP/ERPに関連する制限事項

| 制限事項 | ERP連携への影響 |
|---------|----------------|
| S3 AP（パイプラインは読み取りのみ使用） | ERPへの書き戻しやSAPワークフロートリガー不可 |
| OCR 品質 | スキャン文書の精度はスキャン解像度と紙の品質に依存 |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| ERPマスターデータ | AI分類は抽出IDを参照。ERPマスターデータへのクエリは行わない |
| 多通貨 | 通貨検出と変換は自動ではない。抽出されたまま格納 |
| 法的有効性 | AI分類メタデータは法的文書保存の補完であり代替ではない |

---

## カスタマイズポイント

1. **文書タイプ**: 自社固有のタイプ追加（グループ間請求書、サービス検収シート）
2. **ベンダーマスター**: 抽出されたベンダーIDをSAPベンダーマスター名にマッピング
3. **承認ワークフロー**: 調達決裁権限に合わせた金額閾値を設定
4. **税カテゴリ**: 管轄地域固有の税コードと税率を設定

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

*関連: [use-cases/sap-erp/](../../use-cases/sap-erp/)*
*ペアドキュメント: [industry-sap-erp.md](./industry-sap-erp.md)*
