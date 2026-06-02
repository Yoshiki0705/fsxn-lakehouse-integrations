# Industry Use Cases — Iceberg Metadata Catalog

🌐 [日本語](README-ja.md) | English

## Quick Selection: Find Your Use Case

| Data type | Discovery & Search | Classification & Compliance | AI Enrichment |
|-----------|---|---|---|
| **Text/PDF** | [Legal](legal/) / [Education](education/) | [Financial](financial/) / [Public Sector](public-sector/) | [Legal](legal/) |
| **Images** | [Retail](retail/) / [Insurance](insurance/) | [Healthcare](healthcare/) / [Manufacturing](manufacturing/) | [Defense](defense-satellite/) |
| **CAD/EDA/BIM** | — | [Construction](construction-bim/) | [Semiconductor](semiconductor/) |
| **Video/LiDAR** | — | [Media VFX](media-vfx/) | [Autonomous Driving](autonomous-driving/) |
| **GIS/Geospatial** | — | [Smart City](smart-city/) | [Smart City](smart-city/) |
| **Sensor/IoT** | [Energy](energy/) | [Manufacturing](manufacturing/) | [Genomics](genomics/) |
| **Game Assets** | [Gaming](gaming/) | — | [Gaming](gaming/) |
| **ERP Output** | [SAP/ERP](sap-erp/) | [SAP/ERP](sap-erp/) | — |

## All Use Cases

| # | Industry | Directory | Key file types | Primary value |
|---|----------|-----------|---------------|---------------|
| UC1 | Legal / Compliance | [legal/](legal/) | PDF, DOCX, EML | Contract classification, obligation tracking |
| UC2 | Financial Services | [financial/](financial/) | PDF, XLSX | IDP, KYC/AML, regulatory compliance |
| UC3 | Manufacturing | [manufacturing/](manufacturing/) | STEP, DWG, PDF | Design search, ISO audit, QC traceability |
| UC4 | Media & VFX | [media-vfx/](media-vfx/) | MOV, EXR, WAV | Asset tracking, similarity search |
| UC5 | Healthcare / DICOM | [healthcare/](healthcare/) | DCM, PDF | Image classification, PHI detection |
| UC6 | Semiconductor / EDA | [semiconductor/](semiconductor/) | GDS, OASIS, LEF | Design validation, IP reuse |
| UC7 | Genomics | [genomics/](genomics/) | FASTQ, VCF, BAM | Quality metrics, cross-study discovery |
| UC8 | Energy / Seismic | [energy/](energy/) | SEGY, LAS, CSV | Survey classification, well log search |
| UC9 | Autonomous Driving | [autonomous-driving/](autonomous-driving/) | BAG, PCD, MP4 | Scene classification, annotation tracking |
| UC10 | Construction / BIM | [construction-bim/](construction-bim/) | IFC, RVT, DWG | Version tracking, safety compliance |
| UC11 | Retail / E-Commerce | [retail/](retail/) | JPG, PNG, PSD | Product tagging, catalog completeness |
| UC12 | Logistics | [logistics/](logistics/) | PDF, JPG, CSV | Shipping doc OCR, delivery proof |
| UC13 | Education / Research | [education/](education/) | PDF, DOCX, IPYNB | Paper classification, dataset discovery |
| UC14 | Insurance | [insurance/](insurance/) | JPG, PDF, MP4 | Damage assessment, fraud detection |
| UC15 | Defense / Satellite | [defense-satellite/](defense-satellite/) | TIFF, JP2, NTF | Imagery classification, change detection |
| UC16 | Public Sector | [public-sector/](public-sector/) | PDF, TIFF, CSV | FOIA, PII detection, retention |
| UC17 | Smart City | [smart-city/](smart-city/) | SHP, TIFF, LAS | GIS classification, disaster risk |
| UC18 | Gaming | [gaming/](gaming/) | FBX, DDS, WAV | Asset classification, build tracking |
| UC19 | SAP / ERP | [sap-erp/](sap-erp/) | PDF, XML, CSV | Spool classification, archive search |
| UC20 | Life Sciences | [life-sciences/](life-sciences/) | PDF, XLSX, DCM | Research data management |
| UC21 | Advertising & Marketing | [advertising-marketing/](advertising-marketing/) | PSD, AI, PNG, MP4 | Creative asset tracking, campaign compliance |
| UC22 | Telecommunications | [telecom/](telecom/) | PDF, CFG, PNG | Network config search, tower inspection |
| UC23 | Travel & Hospitality | [travel-hospitality/](travel-hospitality/) | JPG, PDF, DOCX | Property photos, guest docs, maintenance |

## Each Use Case Contains

```
<industry>/
├── README.md              # Overview, business problem, solution fit
├── README-ja.md           # Japanese version
├── schema-extension.yaml  # Industry-specific metadata fields
├── sample-data/
│   └── generate.py        # Sample metadata generator
├── demo/
│   ├── run-demo.sh        # One-command demo
│   └── talking-points.md  # Demo script for presenters
├── cloudformation/
│   └── template.yaml      # Industry-specific infrastructure
└── queries/
    └── named-queries.sql  # Industry-specific Athena queries
```

## Shared Resources

| Resource | Location | Purpose |
|----------|----------|---------|
| Base Iceberg schema | [_shared/base-schema.yaml](_shared/base-schema.yaml) | Common fields all industries share |
| AI classification prompt | [_shared/classification-prompt.py](_shared/classification-prompt.py) | Bedrock prompt template |
| Demo runner framework | [_shared/demo-runner.sh](_shared/demo-runner.sh) | Common demo execution logic |
| Prerequisites check | [../demo/scripts/check-prerequisites.sh](../demo/scripts/check-prerequisites.sh) | Environment validation |
| Infrastructure request | [../docs/infrastructure-request-template.md](../docs/infrastructure-request-template.md) | For platform team |
| Full industry analysis | [../docs/industry-use-cases.md](../docs/industry-use-cases.md) | Detailed ROI + compliance mapping |

## How to Use

```bash
# 1. Check prerequisites
../demo/scripts/check-prerequisites.sh

# 2. Pick your industry
cd use-cases/manufacturing/

# 3. Generate sample data
python ../../demo/sample-data/generate-sample-data.py --industry manufacturing --count 100

# 4. Deploy infrastructure (optional — creates S3 Tables + Athena workgroup)
../_shared/deploy.sh --industry manufacturing --ap-alias <your-alias>

# 5. Run the demo
./demo/run-demo.sh --ap-alias <your-alias>

# 6. Cleanup
../_shared/deploy.sh --delete --industry manufacturing
```

### Deployment Options

| Option | Command | Cost |
|--------|---------|------|
| S3-only (no FSx) | `deploy.sh --industry <name>` | $0 idle |
| With FSx S3 AP | `deploy.sh --industry <name> --ap-alias <alias>` | $0 idle |
| With vector search | `deploy.sh --industry <name> --opensearch` | $0 idle (cold start 10-30s) |
| Delete | `deploy.sh --delete --industry <name>` | — |

## Cross-Reference: Related Repository

This project focuses on **metadata cataloging** (AI classification + Iceberg + search).
For **serverless processing patterns** (Step Functions + Lambda + AI/ML services), see:

→ [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns)

| This repo (Metadata Catalog) | Serverless Patterns repo |
|------------------------------|--------------------------|
| "What files do I have?" | "How do I process them?" |
| Iceberg + Athena + OpenSearch | Step Functions + Lambda + AI/ML |
| Metadata discovery & governance | Automated processing pipelines |
| Read-only access to files | Read + write (processing output) |
