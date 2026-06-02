# 保険業向けデモシナリオ: 保険金請求文書 & 損害評価インテリジェンス

🌐 日本語 | [English](industry-insurance.md)

> 保険金請求文書、医療報告書、損害写真、保険証券を保険会社のファイル共有から自動分類・検索するデモシナリオ。

---

## ビジネスコンテキスト

### 課題

保険会社が直面する課題：

- **請求文書の過負荷**: 保険金請求書、医療報告書、警察報告書、損害評価書が日々数千件、命名規則なく提出
- **不正検知の困難**: 関連する請求文書がシステムに分散し、パターン検出が困難
- **保険証券文書の散在**: 有効な保険証券、裏書、修正がバージョン追跡なく保管
- **査定人の生産性低下**: 関連する過去事例や裏付け文書の検索に複数リポジトリの手動検索が必要

### 解決後の姿

- 請求文書が請求タイプ、重大度、必要アクション別に自動分類
- 「損害額100万円超で査定待ちの自動車保険金請求をすべて表示」が SQL で即座に回答
- 損害写真が重大度推定と不正指標の検出に分析
- セマンティック検索により類似過去請求を発見し、迅速な査定を支援

---

## デモフロー

### ステップ 1: サンプル保険文書を FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry insurance --target /vol/insurance-ops/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `claim-AUTO-2026-08421.pdf` | 保険金請求書 | 自動車衝突事故、230万円見積 |
| `medical-report-CLM08421-injury.pdf` | 医療報告書 | 請求者負傷評価 |
| `damage-photo-CLM08421-front.jpg` | 損害写真 | 車両前部損害、重度 |
| `policy-AUT-P2026-44210.pdf` | 保険証券 | 総合自動車保険 |
| `adjuster-report-CLM08421-final.pdf` | 査定レポート | 最終評価と推奨事項 |

**トークポイント**:
- 「査定人は既存のファイル保存ワークフローを維持 — トレーニング不要」
- 「現場査定人がモバイルからアップロードした写真も同じパイプラインでトリガー」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: claim-AUTO-2026-08421.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: 保険金請求書/自動車
   - 請求 ID: CLM-08421
   - 請求タイプ: 自動車衝突
   - 推定損害額: ¥2,300,000
   - 重大度: 高
   - ステータス: レビュー待ち
   - PII 検出: あり（氏名、住所、免許番号）
   - 不正指標: 検出なし
✅ Classified in 43.5s | Cost: $0.07
```

**トークポイント**:
- 「AI が請求タイプ、重大度、損害見積、不正指標を自動抽出」
- 「損害写真が請求文書との整合性を重大度推定で分析」
- 「PII 検出が内蔵されプライバシーコンプライアンスに対応」
- 「分類信頼度: PoC 精度。本番精度は文書品質により変動」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       claim_id, claim_type, severity, estimated_damage
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'insurance'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | claim_id | claim_type | severity |
|-----------|------------------|:---------:|:--------:|:----------:|:--------:|
| /vol/insurance-ops/claim-AUTO-2026-08421.pdf | 保険金請求書/自動車 | 0.95 | CLM-08421 | 衝突 | 高 |
| /vol/insurance-ops/medical-report-CLM08421-injury.pdf | 医療報告書 | 0.93 | CLM-08421 | 負傷 | 中 |
| /vol/insurance-ops/damage-photo-CLM08421-front.jpg | 損害写真/車両 | 0.91 | CLM-08421 | 衝突 | 高 |
| /vol/insurance-ops/policy-AUT-P2026-44210.pdf | 保険証券/自動車 | 0.97 | - | - | - |
| /vol/insurance-ops/adjuster-report-CLM08421-final.pdf | 査定レポート | 0.94 | CLM-08421 | 衝突 | 高 |

**トークポイント**:
- 「請求関連の全文書が請求 ID で自動的にリンク」
- 「写真分析の損害重大度が請求書の見積と整合性を確認」
- 「PII がプライバシー規制コンプライアンスのためにフラグ付け」

---

### ステップ 4: 保険業務クエリ

**所要時間**: 5 分

```sql
-- 査定レビュー待ちの高額請求
SELECT file_path, claim_id, claim_type, estimated_damage, days_pending
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = '保険金請求書/自動車'
  AND estimated_damage > 1000000
  AND status = 'レビュー待ち'
ORDER BY estimated_damage DESC;

-- 不正指標フラグのある請求
SELECT claim_id, file_path, fraud_indicator_type, confidence_score
FROM s3_tables.metadata_catalog.file_metadata
WHERE fraud_indicators = true
ORDER BY confidence_score DESC;

-- 請求書類の完備チェック
SELECT claim_id,
       COUNT(CASE WHEN ai_classification LIKE '保険金請求書%' THEN 1 END) as forms,
       COUNT(CASE WHEN ai_classification LIKE '損害写真%' THEN 1 END) as photos,
       COUNT(CASE WHEN ai_classification LIKE '医療報告書%' THEN 1 END) as medical
FROM s3_tables.metadata_catalog.file_metadata
WHERE claim_type = '衝突'
GROUP BY claim_id;
```

**トークポイント**:
- 「請求マネージャーが書類完備の高額案件を優先処理」
- 「不正検知チームが疑わしいパターンの自動フラグを取得」
- 「書類完備追跡で請求者との往復を削減」

---

### ステップ 5: 先例検索のためのセマンティック検索

**所要時間**: 5 分

**シナリオ**: 「査定ガイダンスのために類似衝突事故請求を検索」

OpenSearch を使用：
1. **キーワード検索**: `"衝突" AND "前部損害" AND "交差点"` → 完全一致
2. **セマンティック検索**: 「歩行者負傷を伴う交差点での複数車両衝突」→ 類似事例を発見
3. **組み合わせ**: 請求タイプ + 損害額範囲 + セマンティック類似度フィルター

**トークポイント**:
- 「査定人が一貫した査定のために先例を数秒で発見」
- 「異なる記述であってもセマンティック検索が類似請求を発見」
- 「OpenSearch Serverless の注意点: 長時間アイドル後の最初の検索は OCU ウォームアップに 10–30 秒」

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 92% 以上（5 カテゴリ） | PoC 結果。本番は変動あり |
| 処理時間 | 43 秒/ファイル | 単一ファイル。バッチは並行度に依存 |
| 1 ファイルあたりコスト | $0.05–$0.07 | 損害写真: ~$0.05 |
| Athena クエリレスポンス | 2–3 秒 | コールドスタート後（初回: +3–5 秒） |
| OpenSearch レスポンス | <1 秒 | ウォームアップ後（アイドル後: 10–30 秒） |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| 請求文書検索 | 15 分/請求 × 2,000 件/年 → 2 分 | **433 時間削減** |
| 不正パターン検出 | 5 件/月 × 平均 ¥50 万の損失防止 | **¥3,000 万の損失防止** |
| 査定先例検索 | 30 分/件 × 500 件/年 → 5 分 | **208 時間削減** |
| 書類完備追跡 | 10 分/請求 × 2,000 件/年 → 自動化 | **333 時間削減** |

**保守的年間生産性効果**: ~974 時間 × ¥5,000/時 = **¥4,870,000**（~$32,500）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~2,276%

**前提条件**: 50% 利用率、中規模保険会社、不正防止価値は生産性とは別に記載。

---

## 保険業に関連する制限事項

| 制限事項 | 保険業への影響 |
|---------|--------------|
| S3 AP 読み取り専用 | パイプライン経由で解決済み請求を自動アーカイブ不可 |
| S3 Event Notifications 非対応 | S3 イベント経由の下流請求ワークフロートリガー不可 |
| Bedrock 精度の変動 | 医療用語や法的用語にプロンプトチューニングが必要な場合あり |
| 損害写真分析 | AI 重大度推定は補助シグナルのみ — 査定人判断の代替ではない |
| Lambda 一時的アクセス | ファイルコンテンツが Lambda メモリを通過 — zero-copy ストレージ、一時的処理 |
| PII 取り扱い | 請求文書に広範な PII を含む。コンプライアンスとデータ取り扱いポリシーを確認 |
| 不正検出 | AI フラグは指標のみ — 判定ではない。人間によるレビューが必要 |

---

## カスタマイズポイント

1. **請求タイプ**: 自社固有のカテゴリ追加（生命保険、火災保険、賠償責任、専門保険）
2. **重大度閾値**: 内部エスカレーションルールに合わせた損害額ティアを設定
3. **不正指標**: 自社の不正経験に基づくカスタムパターンを定義
4. **規制マッピング**: 管轄地域と保険種目別の文書要件をマッピング

---

*関連: [use-cases/insurance/](../../use-cases/insurance/)*
*ペアドキュメント: [industry-insurance.md](./industry-insurance.md)*
