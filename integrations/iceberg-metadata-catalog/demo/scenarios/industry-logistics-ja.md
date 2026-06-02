# 物流・サプライチェーン向けデモシナリオ: 出荷文書 & 配送証明インテリジェンス

🌐 日本語 | [English](industry-logistics.md)

> 出荷文書、配送写真、通関書類、追跡ログを物流拠点のファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

物流企業が直面する課題：

- **文書量の爆発的増加**: 船荷証券、通関申告書、配送受領書、請求書が日々数千件、地域事務所で生成
- **配送証明の断片化**: ドライバーが撮影した写真や署名がモバイルアップロードとオフィス共有に一貫性なく保管
- **通関コンプライアンスの遅延**: 通関監査のための特定貿易文書の検索に複数システム横断が必要
- **出荷可視性の欠落**: 追跡ログと例外レポートが統一検索機能なく分散

### 解決後の姿

- 出荷文書がアップロード時にタイプ、ルート、運送業者、ステータス別に自動分類
- 「日本発の通関申告で承認待ちのものをすべて表示」が SQL で即座に回答
- 配送証明写真が出荷 ID に紐づき、損傷検知の自動フラグ付け
- 例外レポートと遅延パターンが過去データ全体から検索可能

---

## デモフロー

### ステップ 1: サンプル物流文書を FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry logistics --target /vol/logistics-ops/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `bol-SHP2026060142-JPNLAX.pdf` | 船荷証券 | 日本→LA、コンテナ MSKU7234561 |
| `customs-decl-IMP-2026-08821.pdf` | 通関申告書 | 輸入申告、HS コード 8471.30 |
| `delivery-photo-DEL88421-front.jpg` | 配送写真 | 配送証明、顧客署名あり |
| `tracking-log-SHP2026060142.csv` | 追跡ログ | GPS ウェイポイント、847 エントリ |
| `exception-report-20260601.pdf` | 例外レポート | 日次遅延・損傷サマリ |

**トークポイント**:
- 「ドライバーがモバイルから配送写真をアップロード — ファイル到着時にパイプラインが自動トリガー」
- 「地域事務所は SMB、本社は NFS — 両方とも FPolicy がトリガー」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: bol-SHP2026060142-JPNLAX.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: 船荷証券
   - 出荷 ID: SHP2026060142
   - ルート: 東京 → ロサンゼルス
   - コンテナ: MSKU7234561
   - 運送業者: Ocean Line Co.
   - ステータス: 輸送中
   - 重量: 18,450 kg
✅ Classified in 42.1s | Cost: $0.07
```

**トークポイント**:
- 「AI が出荷 ID、ルート、運送業者、コンテナ情報を自動抽出」
- 「配送写真は損傷指標と署名の有無が分析されます」
- 「分類信頼度: PoC 精度。本番精度は文書品質と言語により変動」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       shipment_id, route, carrier, status
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'logistics'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | shipment_id | route | status |
|-----------|------------------|:---------:|:-----------:|:-----:|:------:|
| /vol/logistics-ops/bol-SHP2026060142-JPNLAX.pdf | 船荷証券 | 0.96 | SHP2026060142 | TYO→LAX | 輸送中 |
| /vol/logistics-ops/customs-decl-IMP-2026-08821.pdf | 通関申告書 | 0.95 | SHP2026060142 | TYO→LAX | 承認待ち |
| /vol/logistics-ops/delivery-photo-DEL88421-front.jpg | 配送証明/写真 | 0.92 | DEL88421 | - | 配送完了 |
| /vol/logistics-ops/tracking-log-SHP2026060142.csv | 追跡ログ | 0.98 | SHP2026060142 | TYO→LAX | 輸送中 |
| /vol/logistics-ops/exception-report-20260601.pdf | 例外レポート | 0.94 | - | 複数 | - |

**トークポイント**:
- 「文書が出荷 ID に自動紐づけされ、エンドツーエンドの可視性を実現」
- 「配送写真で署名の有無が確認済み」
- 「5種類の文書がすべて高精度で分類」

---

### ステップ 4: 物流業務クエリ

**所要時間**: 5 分

```sql
-- 発送国別の通関申告書（承認待ち）
SELECT file_path, shipment_id, origin_country, hs_code, submission_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = '通関申告書'
  AND status = '承認待ち'
ORDER BY submission_date ASC;

-- 損傷が検知された配送写真
SELECT file_path, shipment_id, damage_detected, delivery_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = '配送証明/写真'
  AND damage_detected = true
ORDER BY delivery_date DESC;

-- 過去48時間で例外イベントのある出荷
SELECT shipment_id, exception_type, exception_count, last_event_time
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = '追跡ログ'
  AND exception_count > 0
  AND last_event_time > current_timestamp - interval '48' hour
ORDER BY exception_count DESC;
```

**トークポイント**:
- 「通関チームが承認待ちの申告書を即座に把握」
- 「クレームチームが AI 写真分析で損傷配送を特定」
- 「オペレーションチームがネットワーク全体の例外パターンを追跡」

---

### ステップ 5: 出荷調査のためのセマンティック検索

**所要時間**: 5 分

**シナリオ**: 「出荷 SHP2026060142 に関連するすべての文書を検索」

OpenSearch を使用：
1. **キーワード検索**: `"SHP2026060142"` → この出荷に言及する全文書
2. **セマンティック検索**: 「コンテナ遅延 通関保留 太平洋ルート」→ 類似の遅延パターンを発見
3. **組み合わせ**: ルート + 日付範囲 + セマンティック関連度フィルター

**トークポイント**:
- 「顧客問い合わせ対応で出荷文書パッケージを数秒で組み立て」
- 「セマンティック検索が根本原因分析のために類似過去事例を特定」
- 「OpenSearch Serverless の注意点: 長時間アイドル後の最初の検索は OCU ウォームアップに 10–30 秒」

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 93% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 42 秒/ファイル | 単一ファイル。バッチは並行度に依存 |
| 1 ファイルあたりコスト | $0.05–$0.07 | 配送写真: ~$0.05 |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| 通関文書検索 | 20 分/検索 × 500 検索/年 | **167 時間削減** |
| 配送紛争解決 | 30 分/件 × 200 件/年 → 5 分 | **83 時間削減** |
| 出荷追跡調査 | 15 分/問合せ × 1,000 件/年 | **208 時間削減** |
| 例外パターン分析 | 2 時間/週 手動 → 自動化 | **96 時間削減** |

**保守的年間生産性効果**: ~554 時間 × ¥4,500/時 = **¥2,493,000**（~$16,600）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~1,114%

**前提条件**: 50% 利用率、中規模物流オペレーション、通関ペナルティ削減やクレーム解決迅速化の追加価値は含まず。

---

## 物流業に関連する制限事項

| 制限事項 | 物流業への影響 |
|---------|--------------|
| S3 AP 読み取り専用 | パイプライン経由で完了出荷文書を自動アーカイブ不可 |
| S3 Event Notifications 非対応 | S3 イベント経由の下流ルーティングワークフロートリガー不可 |
| Bedrock 精度の変動 | 多言語貿易文書（EN/JA/CN）はプロンプトチューニングが必要な場合あり |
| 配送写真の品質 | 悪条件でのモバイル写真は損傷検知精度が低下する可能性 |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| リアルタイム要件 | リアルタイム GPS 追跡には非対応。文書処理向け設計 |

---

## カスタマイズポイント

1. **文書カテゴリ**: 運送業者固有のタイプ追加（運送業者請求書、滞船料通知、運賃確認書）
2. **ルートマッピング**: 自社の貿易レーン向けに発着地抽出を設定
3. **コンプライアンスルール**: 国ペア別の文書要件をマッピング
4. **損傷分類**: 梱包、水濡れ、衝撃などの損傷タイプの検知カテゴリを訓練

---

*関連: [use-cases/logistics/](../../use-cases/logistics/)*
*ペアドキュメント: [industry-logistics.md](./industry-logistics.md)*
