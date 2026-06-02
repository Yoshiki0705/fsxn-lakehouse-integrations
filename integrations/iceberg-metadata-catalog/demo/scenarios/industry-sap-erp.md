# SAP / ERP Integration Demo Scenario: Invoice & Purchase Order Intelligence

🌐 [日本語](industry-sap-erp-ja.md) | English

> Automated classification and search of invoice scans, purchase orders, delivery notes, and warehouse receipts that supplement ERP system data.

---

## Business Context

### Challenge

Organizations with SAP/ERP systems face:

- **Paper-digital gap**: Physical invoices, purchase orders, and delivery notes scanned and stored on file shares without ERP linkage
- **Three-way matching delays**: Matching invoices to POs and delivery receipts requires manual document retrieval across systems
- **Archive search difficulty**: Historical documents stored in archival file shares without metadata for efficient retrieval
- **Audit trail gaps**: Supporting documents referenced by ERP transactions exist in disconnected file repositories

### Solution Value

- Scanned ERP documents classified automatically by type, vendor, PO number, and amount
- "Find all unmatched invoices over ¥1M from last month" answered via SQL
- Three-way matching accelerated by linking invoice scans to PO numbers and delivery receipts
- Audit preparation simplified through document-to-transaction linkage

---

## Demo Flow

### Step 1: Place Sample ERP Documents on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry sap-erp --target /vol/erp-docs/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `invoice-scan-VND0042-INV2026-08842.pdf` | Invoice Scan | Vendor invoice, ¥2.4M, raw materials |
| `purchase-order-PO2026-04421.pdf` | Purchase Order | PO for manufacturing parts |
| `delivery-note-DN2026-08842-partial.pdf` | Delivery Note | Partial delivery, 80% of PO quantity |
| `warehouse-receipt-WR2026-08842.pdf` | Warehouse Receipt | Goods received confirmation |
| `credit-memo-CM2026-0042-return.pdf` | Credit Memo | Product return credit |

**Talking points**:
- "Scanned documents from mailroom or receiving dock trigger classification on file arrival"
- "Works alongside SAP ArchiveLink or OpenText — adds AI intelligence on top"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: invoice-scan-VND0042-INV2026-08842.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Invoice
   - Vendor ID: VND-0042
   - Invoice number: INV2026-08842
   - Amount: ¥2,400,000
   - PO reference: PO2026-04421
   - Date: 2026-06-01
   - Category: Raw Materials
   - Tax: ¥240,000 (10%)
   - Payment terms: Net 60
✅ Classified in 43.8s | Cost: $0.07
```

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       vendor_id, document_number, amount, po_reference
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'sap-erp'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | vendor_id | document_number | amount |
|-----------|------------------|:---------:|:---------:|:---------------:|:------:|
| /vol/erp-docs/invoice-scan-VND0042-INV2026-08842.pdf | Invoice | 0.96 | VND-0042 | INV2026-08842 | ¥2.4M |
| /vol/erp-docs/purchase-order-PO2026-04421.pdf | Purchase Order | 0.97 | VND-0042 | PO2026-04421 | ¥3.0M |
| /vol/erp-docs/delivery-note-DN2026-08842-partial.pdf | Delivery Note | 0.94 | VND-0042 | DN2026-08842 | - |
| /vol/erp-docs/warehouse-receipt-WR2026-08842.pdf | Warehouse Receipt | 0.95 | VND-0042 | WR2026-08842 | - |
| /vol/erp-docs/credit-memo-CM2026-0042-return.pdf | Credit Memo | 0.93 | VND-0042 | CM2026-0042 | -¥180K |

---

### Step 4: ERP Operations Queries

**Duration**: 5 minutes

```sql
-- Unmatched invoices (no corresponding delivery note)
SELECT i.vendor_id, i.document_number, i.amount, i.po_reference
FROM s3_tables.metadata_catalog.file_metadata i
WHERE i.ai_classification = 'Invoice'
  AND NOT EXISTS (
    SELECT 1 FROM s3_tables.metadata_catalog.file_metadata d
    WHERE d.ai_classification = 'Delivery Note'
    AND d.po_reference = i.po_reference
  );

-- High-value invoices pending three-way match
SELECT file_path, vendor_id, amount, po_reference, match_status
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Invoice'
  AND amount > 1000000
  AND match_status = 'Pending'
ORDER BY amount DESC;

-- Vendor document completeness
SELECT vendor_id,
       COUNT(CASE WHEN ai_classification = 'Invoice' THEN 1 END) as invoices,
       COUNT(CASE WHEN ai_classification = 'Purchase Order' THEN 1 END) as pos,
       COUNT(CASE WHEN ai_classification = 'Delivery Note' THEN 1 END) as deliveries
FROM s3_tables.metadata_catalog.file_metadata
GROUP BY vendor_id;
```

---

### Step 5: Semantic Search for Audit Support

**Duration**: 5 minutes

**Scenario**: "Find all documents related to PO2026-04421 for audit"

Using OpenSearch:
1. **Keyword search**: `"PO2026-04421"` → all documents referencing this PO
2. **Semantic search**: "raw material procurement from vendor 0042 first half 2026" → finds related transactions
3. **Combined**: Filter by vendor + date range + document type

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 95%+ (5 categories) | PoC result; production varies |
| Processing time | 43 seconds/file | OCR quality impacts accuracy |
| Cost per file | $0.07 | Scanned documents |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Three-way matching | 15 min/invoice × 5,000 invoices/year → 3 min | **1,000 hours saved** |
| Audit document assembly | 3 days/audit → 4 hours × 2 audits/year | **40 hours saved** |
| Invoice dispute resolution | 30 min/dispute × 200 disputes/year → 5 min | **83 hours saved** |
| Duplicate invoice detection | 5 duplicates/month × ¥200K avg. | **¥12M loss prevention** |

**Conservative annual productivity value**: ~1,123 hours × ¥4,000/hr = **¥4,492,000** (~$30,000)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~2,184%

---

## Limitations Relevant to SAP/ERP

| Limitation | Impact for ERP Integration |
|-----------|---------------------------|
| S3 AP read-only | Cannot write back to ERP or trigger SAP workflows |
| OCR quality | Scanned document accuracy depends on scan resolution and paper quality |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| ERP master data | AI classification references extracted IDs; does not query ERP master data |
| Multi-currency | Currency detection and conversion not automatic; extracted as-is |
| Legal validity | AI-classified metadata supplements but does not replace legal document retention |

---

## Customization Points

1. **Document types**: Add company-specific types (intercompany invoices, service entry sheets)
2. **Vendor master**: Map extracted vendor IDs to SAP vendor master names
3. **Approval workflows**: Configure amount thresholds matching procurement delegation authority
4. **Tax categories**: Configure for jurisdiction-specific tax codes and rates

---

## Iceberg Time Travel: Historical Comparison

One unique advantage of the Iceberg table format is time travel — querying metadata as it existed at any past point in time.

```sql
-- View snapshot history
SELECT * FROM s3_tables.metadata_catalog.file_metadata$snapshots
ORDER BY committed_at DESC LIMIT 10;

-- Query metadata as of 24 hours ago
SELECT ai_classification, COUNT(*) as file_count
FROM s3_tables.metadata_catalog.file_metadata
FOR TIMESTAMP AS OF (current_timestamp - interval '24' hour)
GROUP BY ai_classification;

-- Compare current vs. previous classification counts
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

**Use cases for time travel in this industry**:
- Track how file classification distribution changes over time
- Audit what metadata looked like when a compliance decision was made
- Recover from accidental bulk reclassification or deletion
- Compare enrichment pipeline output across different AI model versions


---

*Related: [use-cases/sap-erp/](../../use-cases/sap-erp/)*
*Pair document: [industry-sap-erp-ja.md](./industry-sap-erp-ja.md)*
