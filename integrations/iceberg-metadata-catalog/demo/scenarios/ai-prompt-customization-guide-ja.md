# AIプロンプトカスタマイズガイド: 業界別分類

🌐 日本語 | [English](ai-prompt-customization-guide.md)

> Bedrock Claudeプロンプトを業界ごとにチューニングし、正確なファイル分類とメタデータ抽出を実現する方法。

---

## 目的

AIメタデータカタログはAmazon Bedrock（Claude）を使用してファイルを分類し、構造化メタデータを抽出します。各業界には異なるドキュメントタイプ、専門用語、コンプライアンス要件があります。本ガイドでは、一貫したメタデータスキーマを維持しながら、業界ごとにプロンプトをカスタマイズする方法を示します。

---

## 基本プロンプト構造

すべての分類リクエストは以下の3部構成に従います：

```
┌─────────────────────────────────────┐
│ システムプロンプト                      │  ← 役割、出力形式、制約
├─────────────────────────────────────┤
│ ユーザープロンプト                      │  ← 業界コンテキスト、分類カテゴリ
├─────────────────────────────────────┤
│ ファイルコンテンツ                      │  ← 実際のドキュメントテキスト/画像（presigned URL経由）
└─────────────────────────────────────┘
```

### システムプロンプト（共通）

```text
You are a document classification specialist. Analyze the provided file and return structured JSON metadata.

Rules:
- Return ONLY valid JSON (no markdown, no explanations)
- If uncertain about a field, use null rather than guessing
- confidence_score must be between 0.0 and 1.0
- Set sensitivity_level based on content: public, internal, confidential, or restricted
- If PII/PHI is detected, set pii_detected: true and list types in pii_types array
```

### ユーザープロンプト（業界固有）

ここが業界別カスタマイズのポイントです。以下の例を参照してください。

### ファイルコンテンツ

以下として渡されます：
- **テキスト/PDF**: 抽出されたテキストコンテンツ（最初の10,000文字）
- **画像**: Bedrockマルチモーダル API経由のBase64エンコード
- **構造化データ（CSV/XLSX）**: 最初の50行をテキストとして
- **バイナリ形式**: 抽出されたメタデータ/ヘッダーのみ

---

## 業界別プロンプト例

### 製造業

```text
Classify this file from a manufacturing environment.

Categories: design_drawing, quality_report, bom, meeting_notes, cad_model, 
            inspection_record, process_sheet, material_certificate, 
            maintenance_log, safety_report

Extract if present:
- part_number: Manufacturing part/component ID
- revision: Document revision number
- department: Engineering, QC, Production, Maintenance
- machine_id: Equipment or machine reference
- standard_reference: ISO/JIS/other standard cited
- project_code: Project or product line identifier

Output JSON schema:
{
  "ai_classification": "<category>",
  "confidence_score": <0.0-1.0>,
  "sensitivity_level": "<public|internal|confidential|restricted>",
  "part_number": "<string|null>",
  "revision": "<string|null>",
  "department": "<string|null>",
  "machine_id": "<string|null>",
  "standard_reference": "<string|null>",
  "project_code": "<string|null>",
  "pii_detected": <true|false>,
  "pii_types": []
}
```

### 金融サービス

```text
Classify this document from a financial services context.

Categories: kyc_document, loan_agreement, risk_report, regulatory_filing,
            client_communication, portfolio_report, compliance_certificate,
            audit_report, trade_confirmation, board_minutes

Extract if present:
- customer_id: Client/customer identifier
- document_type: Specific document sub-type
- risk_level: Low, Normal, Medium, High, Critical
- retention_period: Required retention in years
- regulatory_framework: Basel III, MiFID II, JFSA, etc.
- reporting_period: Quarter/year the document covers

Output JSON schema:
{
  "ai_classification": "<category>",
  "confidence_score": <0.0-1.0>,
  "sensitivity_level": "<public|internal|confidential|restricted>",
  "customer_id": "<string|null>",
  "document_type": "<string|null>",
  "risk_level": "<string|null>",
  "retention_period": "<number|null>",
  "regulatory_framework": "<string|null>",
  "reporting_period": "<string|null>",
  "pii_detected": <true|false>,
  "pii_types": []
}
```

### ヘルスケア

```text
Classify this file from a healthcare environment.

Categories: medical_record, lab_result, imaging_report, prescription,
            discharge_summary, consent_form, insurance_claim,
            research_protocol, clinical_trial_data, administrative

If medical record detected, flag as PHI.

Extract if present:
- patient_age_range: Age bracket (0-17, 18-64, 65+) — NOT exact age
- department: Cardiology, Radiology, Emergency, etc.
- procedure_type: Procedure category if applicable
- phi_elements: List of PHI types found (name, DOB, MRN, etc.)
- study_id: Clinical trial or research study identifier
- modality: For imaging — CT, MRI, X-ray, Ultrasound, etc.

IMPORTANT: Do NOT extract or return actual patient identifiers.
Only classify and flag their presence.

Output JSON schema:
{
  "ai_classification": "<category>",
  "confidence_score": <0.0-1.0>,
  "sensitivity_level": "<public|internal|confidential|restricted>",
  "patient_age_range": "<string|null>",
  "department": "<string|null>",
  "procedure_type": "<string|null>",
  "phi_elements": [],
  "study_id": "<string|null>",
  "modality": "<string|null>",
  "pii_detected": <true|false>,
  "pii_types": []
}
```

### 法務

```text
Classify this legal document.

Categories: contract, litigation_filing, corporate_governance,
            compliance_report, intellectual_property, regulatory_submission,
            correspondence, opinion_letter, due_diligence, memorandum

Extract if present:
- case_number: Case or matter reference number
- jurisdiction: Applicable jurisdiction
- document_type: Specific legal document type
- parties_involved: Number of parties (not names)
- effective_date: Document effective date (YYYY-MM-DD)
- privilege_status: privileged, non-privileged, work_product

IMPORTANT: Do NOT extract actual party names or confidential terms.
Only classify document type and structural metadata.

Output JSON schema:
{
  "ai_classification": "<category>",
  "confidence_score": <0.0-1.0>,
  "sensitivity_level": "<public|internal|confidential|restricted>",
  "case_number": "<string|null>",
  "jurisdiction": "<string|null>",
  "document_type": "<string|null>",
  "parties_involved": <number|null>,
  "effective_date": "<string|null>",
  "privilege_status": "<string|null>",
  "pii_detected": <true|false>,
  "pii_types": []
}
```

---

## マルチモーダル対応マトリクス

| ファイルタイプ | Bedrock Claudeサポート | 備考 |
|--------------|:---------------------:|------|
| テキスト/PDF（ネイティブ） | ✅ 完全 | 最高精度。直接テキスト抽出。 |
| 画像（PNG/JPEG） | ✅ Vision | 精度は画像品質と解像度に依存 |
| スキャンPDF | ⚠️ OCR依存 | Amazon Textractで前処理すると最良の結果 |
| Microsoft Office（DOCX/XLSX/PPTX） | ⚠️ 事前抽出要 | テキスト/PDFに変換後に分類 |
| CAD/DWG | ❌ | メタデータのみ抽出（視覚的コンテンツは不可）。ファイルヘッダーを使用。 |
| 音声/動画（MP4/WAV） | ❌ | Amazon Transcribeで最初に文字起こし、その後トランスクリプトを分類 |
| バイナリ科学データ（FASTQ, LiDAR, SEGY） | ❌ | フォーマット固有ライブラリでヘッダー/メタデータのみパース |
| メール（EML/MSG） | ⚠️ パース要 | 件名、本文、添付ファイルを個別に抽出 |

### ファイルタイプ別精度予測

| ファイルタイプ | 予想精度 | 根拠 |
|--------------|:--------:|------|
| テキストPDF（ネイティブ） | 92–96% | クリーンなテキスト、明確な構造 |
| 画像（高解像度） | 88–93% | Visionモデルが良好に処理 |
| 画像（低解像度/圧縮） | 75–85% | 品質劣化が精度に影響 |
| スキャンPDF（Textract使用） | 85–92% | スキャン品質に依存 |
| スキャンPDF（Textractなし） | 60–75% | テキスト画像に対するClaude Vision |
| Officeドキュメント（抽出済み） | 90–95% | テキスト抽出後は良好 |
| メタデータのみ（バイナリヘッダー） | 70–80% | 分類のためのコンテキストが限定的 |

**注**: これらはテストに基づくPoC水準の推定値です。本番精度はドキュメント品質、言語構成、ドメイン固有用語によって異なります。必ず実際のデータで検証してください。

---

## プロンプトチューニングワークフロー

### 1. ベースライン

デフォルトの業界プロンプト（上記の例）から開始し、20〜50のサンプルファイルに対して実行します。

```bash
# サンプルファイルに対して分類を実行
./demo/scripts/classify-batch.sh --industry manufacturing --sample-size 50
```

### 2. テスト

結果をレビューし、誤分類を特定：

```sql
-- 低信頼度の分類を検索
SELECT file_path, ai_classification, confidence_score
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'manufacturing'
  AND confidence_score < 0.85
ORDER BY confidence_score ASC;
```

### 3. 計測

精度メトリクスを計算：

| メトリクス | 計算式 | 目標 |
|-----------|--------|------|
| 精度 | 正解 / 合計 | >90% |
| 低信頼度率 | (スコア < 0.85) / 合計 | <15% |
| Nullフィールド率 | Nullフィールド / 全フィールド | <30% |
| 誤分類率 | 誤カテゴリ / 合計 | <10% |

### 4. 反復改善

一般的な調整：

| 問題 | 解決策 |
|------|--------|
| 誤ったカテゴリが選択される | 例を追加するかカテゴリ説明を明確化 |
| 有効なドキュメントで低信頼度 | ドキュメントタイプをカテゴリリストに追加 |
| フィールドが常にNull | フィールド説明を調整するか同義語を追加 |
| PIIが検出されない | プロンプトに明示的なPIIパターンを追加 |
| 幻覚値（ハルシネーション） | 「不確かな場合はnullを使用」指示を強化 |
| 言語混在の問題 | 「日本語/英語混在コンテンツを処理」を追加 |

### 5. デプロイ

Lambda handler設定のプロンプトを更新：

```yaml
# industry-configs/manufacturing.yaml
classification_prompt:
  system: "..."
  user_template: "..."
  categories:
    - design_drawing
    - quality_report
    # ... 更新されたリスト
  extract_fields:
    - part_number
    - revision
    # ... 更新されたリスト
```

---

## 応用: マルチステップ分類

複数カテゴリにまたがる複雑なドキュメント用：

```text
Step 1: Determine the PRIMARY document type from these categories: [...]
Step 2: If the document contains multiple sections, identify the SECONDARY type.
Step 3: Extract metadata for the PRIMARY type.

Return:
{
  "ai_classification": "<primary_category>",
  "secondary_classification": "<secondary_category|null>",
  ...
}
```

---

## コスト考慮事項

| 要因 | 影響 |
|------|------|
| プロンプト長 | 長いプロンプトは呼び出しあたりコスト増（入力1Kトークンあたり約$0.003） |
| ファイルコンテンツサイズ | 大きなドキュメントはコスト増（10K文字 ≈ 3Kトークン ≈ $0.009） |
| 画像分類 | Vision API価格（Sonnetで画像1枚あたり約$0.04） |
| 低信頼度時のリトライ | プロンプト調整後の再分類で2倍のコスト |

**平均コスト**: テキストドキュメントで$0.05〜$0.07/ファイル、画像で$0.04〜$0.06/ファイル。

---

## ガバナンスとの統合

分類で設定される`sensitivity_level`フィールドがLake Formationアクセスポリシーを直接駆動します：

1. プロンプトがファイルを分類 → `sensitivity_level`を設定
2. Lake Formationデータフィルタが`sensitivity_level`を読み取る
3. 権限のないロールは`restricted`行を参照できない

完全なアクセス制御フローについては[ガバナンス詳細](governance-deep-dive-ja.md)を参照。

---

## Lambda Handlerリファレンス

分類プロンプトはLambda handlerで適用されます：

- Handlerコード: [`lambda/ai-classifier/handler.py`](../../lambda/ai-classifier/handler.py)
- 業界設定: [`demo/sample-data/industry-configs/`](../sample-data/industry-configs/)
- プロンプトテンプレート: 業界別YAML設定に組み込み

---

*関連: [ガバナンス詳細](governance-deep-dive-ja.md) — sensitivity_levelがアクセスをどう駆動するか*
*関連: [Snowflakeアクティベーションパターン](snowflake-activation-pattern-ja.md) — Snowflakeから分類済みメタデータをクエリ*
*ペアドキュメント: [ai-prompt-customization-guide.md](ai-prompt-customization-guide.md)*
