# Industry Use Cases: AI Metadata Catalog for Unstructured Data

🌐 [日本語](industry-use-cases-ja.md) | English

## Executive Summary

This solution makes unstructured files (PDF, images, CAD, video, logs) on existing NAS storage instantly searchable and AI-classifiable — without copying data or changing existing workflows.

**Key value**: Find any file in < 2 seconds via SQL, automatically classify and detect sensitive data, govern access — all for less cost than copying data to S3.

---

## Manufacturing

### Business Problem

| Pain point | Current state | Impact |
|-----------|---------------|--------|
| Finding design documents | Manual folder browsing, asking colleagues | Hours per search, missed deadlines |
| ISO audit document retrieval | Scramble to locate documents before audit | Audit findings, non-conformance risk |
| Quality report traceability | Spreadsheet-based tracking | Incomplete traceability, recall risk |
| Duplicate file detection | Unknown | Wasted storage, version confusion |

### Solution Fit

```
CAD files (.step, .dwg) ──→ AI classification: "engineering drawing"
QC reports (.pdf)       ──→ AI classification: "quality report"
Maintenance logs (.xlsx)──→ AI classification: "maintenance record"
                              │
                              ▼
                    Athena SQL: "Find all QC reports for part P-1234
                                 from last 6 months"
                    Result: < 2 seconds
```

### Demo Scenario (Manufacturing)

```bash
# Generate manufacturing sample data
python demo/sample-data/generate-sample-data.py --industry manufacturing --count 100

# Run demo with manufacturing files
./demo/scripts/run-demo.sh --ap-alias <alias>
```

**Demo talking points**:
- "Find all engineering drawings for pump housing P-2000" → 1.8 seconds
- "Which QC reports mention temperature deviation?" → AI-classified, instant retrieval
- "Show me all files modified since last ISO audit" → Time-range query

### Compliance Mapping

| Requirement | How this solution addresses it |
|-------------|-------------------------------|
| ISO 9001 §7.5 (Document control) | All documents cataloged with metadata, version tracking via Iceberg time travel |
| ISO 9001 §8.5.2 (Traceability) | file_id links to part number, lot, inspection record |
| IATF 16949 (Automotive) | Classification + retention metadata for automotive quality records |
| Document retention | Iceberg snapshot retention + S3 lifecycle policies |
| Access control | Lake Formation grants by department/role |

### ROI Estimate (Manufacturing, 50K files)

| Item | Before | After | Savings |
|------|--------|-------|---------|
| Document search time | 15 min/search × 20 searches/day | < 5 sec/search | **5 hours/day recovered** |
| ISO audit preparation | 2 weeks | 2 days | **8 days saved** |
| Storage (S3 copy eliminated) | $125/month | $0 | **$125/month** |
| AI classification labor | 2 FTE-hours/day | Automated | **$50K/year** |

---

## Public Sector

### Business Problem

| Pain point | Current state | Impact |
|-----------|---------------|--------|
| FOIA/information disclosure requests | Manual search across file shares | Days to weeks response time |
| Personal information inventory | Unknown what files contain PII | Compliance risk |
| Document retention compliance | Manual tracking | Accidental deletion or over-retention |
| Cross-department document sharing | Email attachments, USB drives | Security risk, version confusion |

### Solution Fit

```
Administrative documents ──→ AI classification + PII detection
                              │
                              ├─ PII found → Flag + auto-redact
                              │
                              ▼
                    "Find all documents related to Project X
                     that do NOT contain personal information"
                    → Instant retrieval for disclosure
```

### Demo Scenario (Public Sector)

**Information disclosure workflow**:
1. Request received: "All documents related to infrastructure project ABC"
2. Athena query: `WHERE classification LIKE '%infrastructure%' AND project = 'ABC'`
3. PII check: `WHERE has_pii = true` → Auto-redact before disclosure
4. Audit trail: CloudTrail logs who accessed what, when

### Compliance Mapping

| Requirement | How this solution addresses it |
|-------------|-------------------------------|
| Freedom of Information Act / 情報公開法 | Instant document discovery + PII auto-redaction |
| Personal Information Protection Act / 個人情報保護法 | PII detection (7 types EN, 7 types JA) + anonymization |
| Administrative Document Management Guidelines | Classification + retention metadata + audit trail |
| Data residency | All data stays in same AWS region, no cross-border transfer |
| Access logging | CloudTrail + Lake Formation audit for all metadata queries |

### Procurement Specification Template

For public sector procurement, include these requirements:

```
1. System shall catalog unstructured files without copying or moving original data
2. System shall detect PII in both English and Japanese documents
3. System shall provide SQL-based search with < 5 second response time
4. System shall maintain audit trail of all access to metadata
5. System shall support role-based access control (RBAC)
6. System shall operate within a single AWS region (data residency)
7. System shall provide automatic document classification with confidence scoring
8. System shall support document retention policy enforcement
9. System shall scale to 1M+ files without performance degradation
10. System shall provide cost transparency (pay-per-use, scale-to-zero)
```

---

## Financial Services

### Business Problem

| Pain point | Current state | Impact |
|-----------|---------------|--------|
| Regulatory document retrieval | Manual search for audit/inspection | Regulatory risk, fines |
| KYC/AML document management | Scattered across systems | Compliance gaps |
| Contract clause search | Manual review | Missed obligations, legal risk |
| Data lineage for reporting | Undocumented | Regulatory reporting delays |

### Solution Fit

```
Contracts (.pdf)        ──→ AI: "NDA", "Service Agreement", "Loan Document"
Audit reports (.pdf)    ──→ AI: "Internal Audit", "External Audit", "SOX"
KYC documents (.pdf)    ──→ AI: "KYC", PII detected, sensitivity=restricted
                              │
                              ▼
                    Lake Formation: Only compliance team can see
                    KYC documents. Audit trail for every access.
```

### Compliance Mapping

| Requirement | How this solution addresses it |
|-------------|-------------------------------|
| FSA / 金融庁 inspection readiness | Instant document retrieval with audit trail |
| FISC Security Guidelines | Access control + encryption at rest (SSE-S3) + audit logging |
| Basel III operational risk | Document classification reduces operational risk |
| AML/KYC record retention (7 years) | Iceberg time travel + retention metadata |
| SOX compliance | Immutable audit trail via CloudTrail + Iceberg snapshots |

### ROI Estimate (Financial Services, 200K files)

| Item | Before | After | Savings |
|------|--------|-------|---------|
| Regulatory inspection prep | 4 weeks | 3 days | **17 days saved** |
| Document search (compliance) | 30 min/search | < 5 sec | **Significant FTE recovery** |
| Data breach risk (unknown PII) | High | Quantified + monitored | **Risk reduction** |
| Storage duplication | $500/month | $15/month (metadata only) | **$485/month** |

---

## Healthcare / Life Sciences

### Business Problem

| Pain point | Current state | Impact |
|-----------|---------------|--------|
| Clinical trial document retrieval | Manual search across study folders | Delays in regulatory submissions |
| DICOM image organization | By study ID only, no content search | Missed research opportunities |
| PHI/PII in research data | Unknown extent | HIPAA/個人情報保護法 violation risk |
| Data sharing for collaboration | Manual de-identification | Weeks of delay per request |

### Solution Fit

```
DICOM images (.dcm)     ──→ AI: "MRI Brain", "CT Chest", "Pathology Slide"
Clinical docs (.pdf)    ──→ AI: "Protocol", "Consent Form", "Lab Report"
                              │
                              ├─ PHI detected → Flag + auto-redact
                              │
                              ▼
                    Clean metadata table (no PHI) → Researchers
                    Full metadata table (with PHI) → IRB-approved only
```

### Compliance Mapping

| Requirement | How this solution addresses it |
|-------------|-------------------------------|
| HIPAA Privacy Rule | PHI detection + de-identification + access control |
| 個人情報保護法 (Japan) | PII detection (Japanese) + anonymization |
| 次世代医療基盤法 | Anonymized metadata enables secondary use |
| 3省2ガイドライン | Encryption + access control + audit trail |
| GxP (FDA 21 CFR Part 11) | Immutable audit trail, electronic signatures (via Lake Formation grants) |
| IRB requirements | Data clean room pattern: restricted vs. public metadata tables |

### Data Clean Room Pattern (Healthcare)

```
┌──────────────────────────────────────────┐
│  Restricted Table (IRB-approved only)    │
│  • Patient identifiers (PHI)             │
│  • Raw file paths                        │
│  • Full clinical metadata                │
│  • Access: IRB-approved researchers only │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  Research Table (de-identified)          │
│  • Study ID, modality, body part         │
│  • AI classification + embeddings        │
│  • No PHI, no patient identifiers        │
│  • Access: All approved researchers      │
└──────────────────────────────────────────┘
```

---

## Media & VFX

### Metadata Catalog Value
- AI classification of footage: raw, edited, VFX comp, color grade, audio
- Similarity search: "Find shots similar to this sunset scene"
- Asset tracking: project → scene → take → version lineage
- License/rights metadata: track usage rights per asset

### Key File Types
`.mov`, `.exr`, `.dpx`, `.wav`, `.psd`, `.raw`, `.srt`

### Demo Query
```sql
SELECT file_name, classification, project, scene
FROM metadata WHERE classification = 'raw_footage' AND project = 'Tokyo_Nights'
ORDER BY file_size DESC;
```

---

## Semiconductor / EDA

### Metadata Catalog Value
- GDS/OASIS design file classification and version tracking
- DRC (Design Rule Check) report aggregation across tape-outs
- IP block reuse discovery: "Find all designs using this standard cell library"
- Fab-ready file validation metadata

### Key File Types
`.gds`, `.oasis`, `.lef`, `.def`, `.spice`, `.lib`

### Demo Query
```sql
SELECT file_name, classification, technology_node, design_stage
FROM metadata WHERE file_type = '.gds' AND classification = 'tape_out_ready';
```

---

## Genomics / Life Sciences Research

### Metadata Catalog Value
- FASTQ/VCF/BAM file classification by study, sample, sequencing platform
- Quality metrics extraction (read depth, coverage, variant count)
- Cross-study sample discovery for meta-analysis
- Data sharing compliance (consent status, de-identification)

### Key File Types
`.fastq`, `.vcf`, `.bam`, `.cram`, `.bed`, `.gtf`

### Demo Query
```sql
SELECT file_name, study_id, sample_type, sequencing_platform
FROM metadata WHERE classification = 'whole_genome' AND quality_score > 30;
```

---

## Energy / Seismic

### Metadata Catalog Value
- SEG-Y seismic survey classification by area, vintage, processing stage
- Well log metadata extraction and cross-referencing
- Pipeline inspection report discovery
- Environmental compliance document tracking

### Key File Types
`.segy`, `.las`, `.csv` (SCADA), `.pdf` (inspection reports), `.tiff` (thermal)

### Demo Query
```sql
SELECT file_name, survey_area, acquisition_date, processing_stage
FROM metadata WHERE classification = 'seismic_survey' AND survey_area = 'Block-A';
```

---

## Autonomous Driving / ADAS

### Metadata Catalog Value
- Driving scene classification: highway, urban, intersection, parking
- Sensor data inventory: camera, LiDAR, radar, GPS/IMU
- Annotation status tracking for ML training datasets
- Weather/lighting condition metadata for scenario coverage

### Key File Types
`.bag` (ROS), `.pcd` (point cloud), `.mp4`, `.json` (annotations), `.csv` (CAN bus)

### Demo Query
```sql
SELECT file_name, scene_type, weather, time_of_day, annotation_status
FROM metadata WHERE scene_type = 'intersection' AND annotation_status = 'pending';
```

---

## Construction / BIM

### Metadata Catalog Value
- IFC/Revit model version tracking across project phases
- Drawing OCR for specification extraction
- Safety compliance document classification
- As-built vs design comparison metadata

### Key File Types
`.ifc`, `.rvt`, `.dwg`, `.pdf` (drawings), `.jpg` (site photos)

### Demo Query
```sql
SELECT file_name, project_phase, discipline, revision
FROM metadata WHERE classification = 'structural_drawing' AND project = 'Tower-A';
```

---

## Retail / E-Commerce

### Metadata Catalog Value
- Product image auto-tagging (color, category, style, season)
- Catalog completeness tracking (which products lack images?)
- Brand asset management and license tracking
- User-generated content moderation metadata

### Key File Types
`.jpg`, `.png`, `.tiff` (product photos), `.psd`, `.ai` (design files)

### Demo Query
```sql
SELECT file_name, product_category, color, season, has_model
FROM metadata WHERE classification = 'product_photo' AND season = '2026-SS';
```

---

## Logistics / Supply Chain

### Metadata Catalog Value
- Shipping document OCR and classification (BOL, invoice, customs)
- Warehouse inventory image analysis
- Delivery proof photo management
- Cross-border compliance document tracking

### Key File Types
`.pdf` (shipping docs), `.jpg` (delivery proof), `.csv` (tracking), `.xlsx` (manifests)

### Demo Query
```sql
SELECT file_name, document_type, shipment_id, origin_country
FROM metadata WHERE classification = 'customs_declaration' AND origin_country = 'CN';
```

---

## Education / Research

### Metadata Catalog Value
- Research paper classification by field, methodology, funding source
- Dataset discovery across departments and labs
- Thesis/dissertation version tracking
- Open access compliance metadata

### Key File Types
`.pdf` (papers), `.docx` (theses), `.csv`/`.parquet` (datasets), `.ipynb` (notebooks)

### Demo Query
```sql
SELECT file_name, research_field, publication_year, open_access_status
FROM metadata WHERE classification = 'journal_paper' AND research_field = 'genomics';
```

---

## Insurance

### Metadata Catalog Value
- Claims photo damage assessment (AI severity scoring)
- Policy document classification and clause extraction
- Fraud detection: duplicate image detection across claims
- Underwriting document organization

### Key File Types
`.jpg` (damage photos), `.pdf` (policies, claims), `.xlsx` (actuarial), `.mp4` (surveillance)

### Demo Query
```sql
SELECT file_name, claim_id, damage_severity, fraud_risk_score
FROM metadata WHERE classification = 'vehicle_damage' AND damage_severity >= 0.7;
```

---

## Defense / Satellite

### Metadata Catalog Value
- Satellite imagery classification (land use, change detection, object detection)
- Security classification level tracking (UNCLASSIFIED → SECRET)
- Temporal analysis: same location across multiple acquisition dates
- Multi-sensor fusion metadata (optical, SAR, multispectral)

### Key File Types
`.tiff` (GeoTIFF), `.jp2`, `.ntf` (NITF), `.shp`, `.kml`

### Demo Query
```sql
SELECT file_name, acquisition_date, sensor_type, cloud_cover_pct, classification_level
FROM metadata WHERE geographic_area = 'AOI-7' AND cloud_cover_pct < 10;
```

---

## Smart City / Geospatial

### Metadata Catalog Value
- GIS data classification (parcels, utilities, zoning, elevation)
- Urban planning document discovery
- Disaster risk mapping metadata
- Citizen service request document tracking

### Key File Types
`.shp`, `.geojson`, `.tiff` (DEM/DSM), `.las` (LiDAR), `.pdf` (planning docs)

### Demo Query
```sql
SELECT file_name, data_layer, coordinate_system, last_updated
FROM metadata WHERE classification = 'zoning_map' AND district = 'Central';
```

---

## Legal / Compliance (Law Firms)

### Metadata Catalog Value
- Contract classification (NDA, MSA, SLA, employment, lease)
- Clause extraction and obligation tracking
- Matter-based document organization
- Privilege log automation (attorney-client privilege detection)

### Key File Types
`.pdf`, `.docx` (contracts), `.msg`/`.eml` (emails), `.xlsx` (privilege logs)

### Demo Query
```sql
SELECT file_name, contract_type, counterparty, expiration_date, has_auto_renewal
FROM metadata WHERE classification = 'service_agreement' AND expiration_date < '2026-12-31';
```

---

## Gaming / Build Pipeline

### Metadata Catalog Value
- Game asset classification (texture, model, animation, audio, shader)
- Build artifact tracking across platforms (PC, console, mobile)
- Asset dependency mapping
- Localization completeness tracking

### Key File Types
`.fbx`, `.png`/`.dds` (textures), `.wav`/`.ogg` (audio), `.unity`/`.uasset`, `.zip` (builds)

### Demo Query
```sql
SELECT file_name, asset_type, target_platform, build_version, file_size
FROM metadata WHERE asset_type = 'texture' AND file_size > 10000000
ORDER BY file_size DESC;
```

---

## SAP / ERP Adjacent

### Metadata Catalog Value
- SAP spool output classification (invoices, delivery notes, reports)
- Archive file discovery for audit (IDoc, BAPI logs)
- Cross-system document linking (SAP document number → file on NAS)
- Retention policy enforcement for ERP-generated documents

### Key File Types
`.pdf` (spool output), `.xml` (IDoc), `.csv` (exports), `.xlsx` (reports)

### Demo Query
```sql
SELECT file_name, sap_document_number, document_type, creation_date
FROM metadata WHERE classification = 'sap_invoice' AND creation_date >= '2026-01-01';
```

---

## Decision Framework: Is This Right for Your Organization?

### When to Use This Solution

| ✅ Good fit | ❌ Not a fit |
|------------|-------------|
| Large volume of unstructured files (10K+) on NAS | Structured data only (databases, data warehouses) |
| Files are difficult to find or classify | Files are already well-organized and searchable |
| Regulatory requirements for document governance | No compliance requirements |
| Multiple teams need access to same files | Single user/team with simple folder structure |
| AI classification would save significant manual effort | Files don't benefit from classification |
| Existing NFS/SMB workflows must not change | Willing to migrate all data to a new system |

### Comparison with Existing Solutions

| Capability | SharePoint/Box | This Solution | Traditional DMS |
|-----------|:---:|:---:|:---:|
| Search speed (100K files) | Seconds | < 2 seconds | Seconds |
| AI classification | Limited | ✅ Full (Vision + NLP) | Limited |
| PII detection (EN + JA) | Limited | ✅ Automatic | Manual |
| Zero-copy (no data movement) | ❌ | ✅ | ❌ |
| NFS/SMB compatibility | ❌ | ✅ | ❌ |
| SQL query interface | ❌ | ✅ | ❌ |
| Scale-to-zero cost | ❌ | ✅ | ❌ |
| Multi-engine access (Athena/Spark/Trino) | ❌ | ✅ | ❌ |
| Iceberg time travel | ❌ | ✅ | Version history |
| Storage deduplication | ❌ | ✅ (ONTAP) | ❌ |

### PoC Proposal Template (for Internal Approval)

**Title**: AI Metadata Catalog PoC — Unstructured Data Discovery & Governance

**Objective**: Evaluate feasibility of making [X] files on existing NAS instantly searchable and AI-classifiable without data migration.

**Scope**:
- Target: [Volume/Share name] containing [file types]
- File count: [estimated]
- Duration: 2 weeks (1 week setup, 1 week evaluation)

**Expected outcomes**:
- File discovery time: Minutes → Seconds
- PII inventory: Unknown → Quantified
- Document classification: Manual → Automated
- Cost: < $100 for entire PoC

**Resources needed**:
- FSx for ONTAP S3 Access Point (read-only, see infrastructure-request-template.md)
- AWS account with Bedrock, Athena, S3 Tables access
- 1 data engineer (part-time, 1 week)

**Success criteria**:
- [ ] 100+ files cataloged and searchable via SQL
- [ ] AI classification accuracy > 80% on sample set
- [ ] PII detection identifies known sensitive files
- [ ] Query response time < 5 seconds
- [ ] Total PoC cost < $100

**Risk**: Zero. Read-only access to existing files. No data movement. No workflow changes. Fully reversible (delete CloudFormation stack).

---

## Next Steps

1. **Try the S3-only quickstart** (10 min, no infrastructure needed): [quickstart-s3-only.md](../demo/docs/quickstart-s3-only.md)
2. **Request infrastructure** (send to platform team): [infrastructure-request-template.md](infrastructure-request-template.md)
3. **Run the full demo** (15 min, requires FSx S3 AP): [demo-guide.md](../demo/docs/demo-guide.md)
4. **Review architecture**: [Architecture Document](../../docs/en/iceberg-metadata-catalog.md)
