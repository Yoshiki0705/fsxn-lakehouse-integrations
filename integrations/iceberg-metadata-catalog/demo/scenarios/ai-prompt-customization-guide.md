# AI Prompt Customization Guide: Per-Industry Classification

🌐 [日本語](ai-prompt-customization-guide-ja.md) | English

> How to tune Bedrock Claude prompts for different industries to achieve accurate file classification and metadata extraction.

---

## Purpose

The AI Metadata Catalog uses Amazon Bedrock (Claude) to classify files and extract structured metadata. Each industry has different document types, terminology, and compliance requirements. This guide shows how to customize prompts per industry while maintaining a consistent metadata schema.

---

## Base Prompt Structure

Every classification request follows this three-part structure:

```
┌─────────────────────────────────────┐
│ System Prompt                       │  ← Role, output format, constraints
├─────────────────────────────────────┤
│ User Prompt                         │  ← Industry context, classification categories
├─────────────────────────────────────┤
│ File Content                        │  ← Actual document text/image (via presigned URL)
└─────────────────────────────────────┘
```

### System Prompt (Common)

```text
You are a document classification specialist. Analyze the provided file and return structured JSON metadata.

Rules:
- Return ONLY valid JSON (no markdown, no explanations)
- If uncertain about a field, use null rather than guessing
- confidence_score must be between 0.0 and 1.0
- Set sensitivity_level based on content: public, internal, confidential, or restricted
- If PII/PHI is detected, set pii_detected: true and list types in pii_types array
```

### User Prompt (Industry-Specific)

This is where per-industry customization happens. See examples below.

### File Content

Passed as:
- **Text/PDF**: Extracted text content (first 10,000 characters)
- **Images**: Base64-encoded via Bedrock multimodal API
- **Structured data (CSV/XLSX)**: First 50 rows as text
- **Binary formats**: Extracted metadata/headers only

---

## Industry-Specific Prompt Examples

### Manufacturing

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

### Financial Services

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

### Healthcare

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

### Legal

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

## Multimodal Capability Matrix

| File Type | Bedrock Claude Support | Notes |
|-----------|:---------------------:|-------|
| Text/PDF (native) | ✅ Full | Best accuracy. Direct text extraction. |
| Images (PNG/JPEG) | ✅ Vision | Accuracy depends on image quality and resolution |
| Scanned PDF | ⚠️ OCR-dependent | Pre-process with Amazon Textract for best results |
| Microsoft Office (DOCX/XLSX/PPTX) | ⚠️ Extract first | Convert to text/PDF before classification |
| CAD/DWG | ❌ | Extract metadata only (not visual content). Use file headers. |
| Audio/Video (MP4/WAV) | ❌ | Use Amazon Transcribe first, then classify transcript |
| Binary scientific (FASTQ, LiDAR, SEGY) | ❌ | Parse headers/metadata only via format-specific libraries |
| Email (EML/MSG) | ⚠️ Parse first | Extract subject, body, attachments separately |

### Accuracy Expectations by File Type

| File Type | Expected Accuracy | Rationale |
|-----------|:-----------------:|-----------|
| Text PDF (native) | 92–96% | Clean text, clear structure |
| Image (high-res) | 88–93% | Vision model handles well |
| Image (low-res/compressed) | 75–85% | Quality degradation impacts accuracy |
| Scanned PDF (with Textract) | 85–92% | Depends on scan quality |
| Scanned PDF (without Textract) | 60–75% | Claude vision on image of text |
| Office documents (extracted) | 90–95% | Good after text extraction |
| Metadata-only (binary headers) | 70–80% | Limited context for classification |

**Note**: These are PoC-level estimates based on testing. Production accuracy varies by document quality, language mix, and domain-specific terminology. Always validate with your actual data.

---

## Prompt Tuning Workflow

### 1. Baseline

Start with the default industry prompt (examples above) and run against 20–50 sample files.

```bash
# Run classification against sample files
./demo/scripts/classify-batch.sh --industry manufacturing --sample-size 50
```

### 2. Test

Review results and identify misclassifications:

```sql
-- Find low-confidence classifications
SELECT file_path, ai_classification, confidence_score
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'manufacturing'
  AND confidence_score < 0.85
ORDER BY confidence_score ASC;
```

### 3. Measure

Calculate accuracy metrics:

| Metric | Formula | Target |
|--------|---------|--------|
| Accuracy | correct / total | >90% |
| Low-confidence rate | (score < 0.85) / total | <15% |
| Null field rate | null fields / total fields | <30% |
| Misclassification rate | wrong category / total | <10% |

### 4. Iterate

Common adjustments:

| Problem | Solution |
|---------|----------|
| Wrong category chosen | Add examples or clarify category descriptions |
| Low confidence on valid docs | Add the document type to categories list |
| Fields consistently null | Adjust field descriptions or add synonyms |
| PII not detected | Add explicit PII patterns to prompt |
| Hallucinated values | Strengthen "use null if uncertain" instruction |
| Language mix issues | Add "Handle Japanese/English mixed content" |

### 5. Deploy

Update the prompt in the Lambda handler configuration:

```yaml
# industry-configs/manufacturing.yaml
classification_prompt:
  system: "..." 
  user_template: "..."
  categories:
    - design_drawing
    - quality_report
    # ... updated list
  extract_fields:
    - part_number
    - revision
    # ... updated list
```

---

## Advanced: Multi-Step Classification

For complex documents that span multiple categories:

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

## Cost Considerations

| Factor | Impact |
|--------|--------|
| Prompt length | Longer prompts cost more per invocation (~$0.003 per 1K input tokens) |
| File content size | Larger documents cost more (10K chars ≈ 3K tokens ≈ $0.009) |
| Image classification | Vision API pricing (~$0.04 per image for Sonnet) |
| Retry on low confidence | 2x cost if re-classifying with adjusted prompt |

**Average cost**: $0.05–$0.07 per file (text documents), $0.04–$0.06 per image.

---

## Integration with Governance

The `sensitivity_level` field set by classification directly drives Lake Formation access policies:

1. Prompt classifies file → sets `sensitivity_level`
2. Lake Formation data filter reads `sensitivity_level`
3. Unauthorized roles cannot see `restricted` rows

See [Governance Deep Dive](governance-deep-dive.md) for the full access control flow.

---

## Lambda Handler Reference

The classification prompts are applied in the Lambda handler:

- Handler code: [`lambda/ai-classifier/handler.py`](../../lambda/ai-classifier/handler.py)
- Industry configs: [`demo/sample-data/industry-configs/`](../sample-data/industry-configs/)
- Prompt templates: Embedded in YAML config per industry

---

*Related: [Governance Deep Dive](governance-deep-dive.md) — how sensitivity_level drives access*
*Related: [Snowflake Activation Pattern](snowflake-activation-pattern.md) — querying classified metadata from Snowflake*
*Pair document: [ai-prompt-customization-guide-ja.md](ai-prompt-customization-guide-ja.md)*
