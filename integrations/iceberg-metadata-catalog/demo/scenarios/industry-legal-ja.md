# 法務業向けデモシナリオ: 契約書 & 案件文書 AI 分類

> 法律事務所・法務部門の文書検索、案件管理、保存期限管理を改善するデモシナリオ

---

## ビジネスコンテキスト

### 課題

法務チームが直面する課題：

- **文書ディスカバリの負荷**: 訴訟やデューデリジェンスで数年分の案件ファイルから関連文書を探すのに数週間
- **契約ライフサイクルの把握不足**: ファイル共有上の数千件の契約書で更新日・条件・期限が見えない
- **秘匿特権文書の識別**: ディスカバリ時に特権文書を迅速に特定することが困難
- **ナレッジ再利用不足**: 過去の調査・意見書が非構造化ファイルシステムの中に埋没

### 解決後の姿

- 法務文書が種類別（契約書、訴状、意見書、書信）に自動分類
- 契約書メタデータ（当事者、日付、主要条件）が抽出されライフサイクル管理に活用
- 秘匿特権の可能性がある文書が自動フラグ付け（レビュー対象として）
- 過去の案件調査がセマンティック検索で発見可能

---

## デモフロー

### ステップ 1: サンプル法務文書を FSx に配置

**所要時間**: 2 分

```bash
./demo/scripts/upload-sample-data.sh --industry legal --target /vol/legal/
```

**サンプルファイル**:

| ファイル名 | 種類 | 説明 |
|-----------|------|------|
| `nda-acme-corp-2025-renewal.pdf` | 契約書/NDA | 秘密保持契約（更新条項あり） |
| `litigation-brief-case-2026-0042.docx` | 訴状 | 略式判決申立書 |
| `legal-opinion-ip-transfer-20260115.pdf` | 法律意見書 | IP 譲渡分析 |
| `client-email-privilege-matter-789.msg` | 秘匿特権通信 | 弁護士・依頼者間特権メール |
| `due-diligence-checklist-MA-2026.xlsx` | デューデリジェンス | M&A 取引文書チェックリスト |

**トークポイント**:
- 「弁護士やパラリーガルは通常通り文書を保存 — AI 分類は透過的に実行」
- 「NFS (Linux/Mac) と SMB (Windows) の両方で動作」
- 「注意: 処理中にファイルコンテンツが Lambda メモリを通過（一時的、永続化されない）」

---

### ステップ 2: FPolicy 検知 → AI 自動分類

**所要時間**: 約 42 秒/ファイル（自動）

```
📄 Processing: nda-acme-corp-2025-renewal.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - 文書種別: 契約書/NDA
   - 当事者: [当方依頼者], Acme Corporation
   - 締結日: 2025-03-15
   - 期限: 2026-03-14
   - 自動更新: あり（30 日前通知必要）
   - 主要条件: 秘密保持、競業避止（2 年）
   - 秘匿特権: なし
✅ Classified in 44.2s | Cost: $0.07
```

**トークポイント**:
- 「AI が契約書から構造化メタデータを抽出 — 当事者、日付、更新条件」
- 「秘匿特権の可能性はレビュー対象としてフラグ付け（確定判断ではない）」
- 「信頼度: テストデータでの PoC 平均 0.94。本番精度は変動 — 複雑な法律用語や多言語契約はプロンプトチューニングが必要な場合あり」

---

### ステップ 3: 分類結果の確認

**所要時間**: 3 分

```sql
SELECT file_path, ai_classification, confidence_score,
       document_parties, expiry_date, privilege_flag, matter_id
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'legal'
ORDER BY scan_timestamp DESC;
```

**期待される結果**:

| file_path | ai_classification | confidence | privilege_flag | expiry_date |
|-----------|------------------|:---------:|:--------------:|:----------:|
| .../nda-acme-corp-2025-renewal.pdf | 契約書/NDA | 0.95 | なし | 2026-03-14 |
| .../litigation-brief-case-2026-0042.docx | 訴状/準備書面 | 0.94 | なし | - |
| .../legal-opinion-ip-transfer-20260115.pdf | 法律意見書 | 0.93 | ワークプロダクト | - |
| .../client-email-privilege-matter-789.msg | 書信 | 0.91 | 弁護士・依頼者間 | - |
| .../due-diligence-checklist-MA-2026.xlsx | デューデリジェンス | 0.94 | なし | - |

**注意**: 信頼度は PoC 結果。秘匿特権の分類は AI 補助であり、特権主張には弁護士レビューが必須です。

---

### ステップ 4: 契約ライフサイクルクエリ

**所要時間**: 5 分

```sql
-- 60 日以内に期限切れの契約書
SELECT file_path, document_parties, expiry_date, auto_renewal,
       renewal_notice_days
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE '契約書%'
  AND expiry_date BETWEEN current_date AND current_date + interval '60' day
ORDER BY expiry_date ASC;

-- 特定案件の秘匿特権文書
SELECT file_path, ai_classification, privilege_flag, creation_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE matter_id = 'CASE-2026-0042'
  AND privilege_flag IS NOT NULL
ORDER BY creation_date DESC;

-- デューデリジェンス文書インベントリ
SELECT ai_classification, count(*) as doc_count,
       min(creation_date) as earliest, max(creation_date) as latest
FROM s3_tables.metadata_catalog.file_metadata
WHERE matter_id = 'MA-2026'
GROUP BY ai_classification;
```

**トークポイント**:
- 「手動カレンダー管理が必要だった契約更新追跡が SQL クエリに」
- 「プリビレッジログ作成時間が数日から数時間に短縮」
- 「注意: アイドル後の最初の Athena クエリ: 3–5 秒コールドスタート」

---

### ステップ 5: セマンティック検索で過去の調査を発見

**所要時間**: 5 分

**シナリオ**: 「クロスボーダー取引における IP 譲渡に関する過去の法律意見書を検索」

OpenSearch セマンティック検索：
- 「知的財産 移転 国際 管轄」→ 関連する意見書を発見
- フィルター: `ai_classification = '法律意見書'` + セマンティック関連度

**トークポイント**:
- 「アソシエイトがシニアパートナーに聞かずに過去の関連作業を発見」
- 「セマンティック検索は異なる用語でも概念的に関連する文書を見つけます」
- 「OpenSearch ウォームアップ: 長時間アイドル後 10–30 秒」

---

## 期待される結果

| 指標 | 目標値 | 注意事項 |
|------|--------|---------|
| 分類精度 | 90% 以上（5 カテゴリ） | PoC 結果。複雑な法律用語で精度低下の可能性 |
| 処理時間 | 42 秒/ファイル | 標準文書 |
| 1 ファイルあたりコスト | $0.07 | 100KB–1MB 文書 |
| 契約メタデータ抽出 | 85%+ の契約で主要フィールド抽出 | 複雑な多当事者契約は抽出率低下の可能性 |
| 特権フラグ | 高い再現率（見落とし少） | 偽陽性あり — 人的レビュー必須 |

---

## ROI ストーリー（保守的見積もり）

| 項目 | 計算 | 年間効果 |
|------|------|:-------:|
| 文書ディスカバリ | 2 週間 → 2 日 × 年 10 案件 | **800 時間削減** |
| 契約更新追跡 | 30 分/契約 × 200 契約 | **100 時間削減** |
| 過去調査の発見 | 4 時間 → 30 分 × 年 100 回検索 | **350 時間削減** |
| プリビレッジログ作成 | 3 日 → 4 時間 × 年 5 案件 | **130 時間削減** |

**保守的年間生産性効果**: ~1,380 時間 × ¥8,000/時（法務レート） = **¥11,040,000**（~$73,600）
**年間ソリューションコスト**: ~$1,368
**保守的 ROI**: ~5,280%

**前提条件**: 50% 利用率、保守的時間見積もり。法務時給はパラリーガル/アソシエイトの混合。

---

## 法務業に関連する制限事項

| 制限事項 | 法務への影響 |
|---------|------------|
| 秘匿特権分類は AI 補助 | 確定判断ではない — 特権主張には弁護士レビュー必須 |
| Lambda 一時的処理 | 秘匿/機密コンテンツが Lambda メモリを通過 — IT セキュリティと評価 |
| Bedrock 精度の変動 | 多言語契約、手書き注釈、専門法律用語で精度低下 |
| S3 AP 読み取り専用 | 訴訟ホールド通知の自動適用やリティゲーションホールドストレージへの自動移動不可 |
| S3 Event Notifications 非対応 | S3 イベント経由の案件管理システム更新自動トリガー不可 |
| 複雑な契約 | 多当事者・多管轄契約はメタデータ抽出精度が低い場合あり |

---

## カスタマイズポイント

1. **分類カテゴリ**: 事務所固有の文書タイプ追加（委任状、請求メモ等）
2. **契約フィールド**: 管轄地域固有の条件抽出を設定（準拠法、紛争解決条項）
3. **特権インジケーター**: 事務所の特権分類アプローチに合わせたプロンプトチューニング
4. **案件管理**: 文書-案件関連付けのための案件 ID 統合
5. **保存ポリシー**: 文書タイプを弁護士職責上の保存要件にマッピング

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

*関連設定: [`legal.yaml`](../sample-data/industry-configs/legal.yaml)*
*ペアドキュメント: [industry-legal.md](./industry-legal.md)*
