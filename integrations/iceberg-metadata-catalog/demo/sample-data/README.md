# Industry Sample Data for Demo

🌐 [日本語](README-ja.md) | English

## Overview

This directory provides sample data references and generation scripts for industry-specific demos. Each industry dataset demonstrates the metadata catalog's value for that sector's unstructured data.

## Industry Datasets

### Manufacturing (設計・製造)

| Data Type | Source | License | Size | Demo Use |
|-----------|--------|---------|------|----------|
| CAD files (STEP/STL) | [GrabCAD Community](https://grabcad.com/library) | CC-BY / Free | Varies | Design document similarity search |
| Engineering drawings (PDF) | [NASA Technical Reports](https://ntrs.nasa.gov/) | Public Domain | 1-50MB | Document classification |
| Product images | [MVTec Anomaly Detection](https://www.mvtec.com/company/research/datasets/mvtec-ad) | CC-BY-NC-SA 4.0 | 4.9GB | Quality inspection AI |
| IoT sensor data | [NASA Turbofan Engine Degradation](https://data.nasa.gov/Aerospace/CMAPSS-Jet-Engine-Simulated-Data/ff5v-kuh6) | Public Domain | 26MB | Predictive maintenance |

### Financial Services (金融)

| Data Type | Source | License | Size | Demo Use |
|-----------|--------|---------|------|----------|
| Invoice images | [SROIE Dataset](https://rrc.cvc.uab.es/?ch=13) | Research | 36MB | Invoice classification + OCR |
| Document images | [RVL-CDIP](https://huggingface.co/datasets/rvl_cdip) | Research | 38GB | Document type classification |
| Financial reports (PDF) | [SEC EDGAR](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany) | Public Domain | Varies | Compliance search |
| Contract samples | [CUAD Dataset](https://www.atticusprojectai.org/cuad) | CC-BY-4.0 | 80MB | Contract clause extraction |

### Healthcare (医療)

| Data Type | Source | License | Size | Demo Use |
|-----------|--------|---------|------|----------|
| Medical images (DICOM) | [NIH Chest X-rays](https://nihcc.app.box.com/v/ChestXray-NIHCC) | CC0 1.0 | 42GB | DICOM anonymization demo |
| Medical images (DICOM) | [TCIA Collections](https://www.cancerimagingarchive.net/) | Various (CC-BY) | Varies | Medical image classification |
| Clinical documents | [MIMIC-III Clinical Notes](https://physionet.org/content/mimiciii/) | PhysioNet License | 6GB | PII detection in medical text |
| Pathology images | [Camelyon16](https://camelyon16.grand-challenge.org/) | CC0 1.0 | 700GB | Whole slide image analysis |

### Media & Entertainment (メディア)

| Data Type | Source | License | Size | Demo Use |
|-----------|--------|---------|------|----------|
| Images (diverse) | [Open Images V7](https://storage.googleapis.com/openimages/web/index.html) | CC-BY-4.0 | 561GB | Image classification + tagging |
| Video clips | [Kinetics-700](https://www.deepmind.com/open-source/kinetics) | CC-BY-4.0 | Large | Video scene classification |
| Audio recordings | [Common Voice](https://commonvoice.mozilla.org/) | CC0 | 90GB+ | Audio transcription |
| Stock photos | [Unsplash Dataset](https://unsplash.com/data) | Unsplash License | 25GB | Photo similarity search |

### Public Sector (公共)

| Data Type | Source | License | Size | Demo Use |
|-----------|--------|---------|------|----------|
| Satellite imagery | [Sentinel-2 on AWS](https://registry.opendata.aws/sentinel-2/) | Copernicus | PB-scale | Geospatial classification |
| Government documents | [US Government Publishing Office](https://www.govinfo.gov/) | Public Domain | Varies | Document search + PII |
| Census data | [US Census Bureau](https://data.census.gov/) | Public Domain | Varies | Demographic analysis |
| Weather data | [NOAA NEXRAD on AWS](https://registry.opendata.aws/noaa-nexrad/) | Public Domain | 270TB | Sensor data patterns |

### Energy & Utilities (エネルギー)

| Data Type | Source | License | Size | Demo Use |
|-----------|--------|---------|------|----------|
| Wind turbine data | [Engie Open Data](https://opendata-renewables.engie.com/) | Open License | Varies | Predictive maintenance |
| Power grid logs | [Pecan Street Dataport](https://www.pecanstreet.org/dataport/) | Research | Varies | Anomaly detection |
| Seismic data | [SEG Open Data](https://wiki.seg.org/wiki/Open_data) | Various | Varies | Subsurface analysis |
| Solar panel images | [DeepSolar](https://web.stanford.edu/group/deepsolar/) | Research | 1.3M images | Asset inspection |

## Platform-Specific Sample Data

### Databricks

| Dataset | Source | Use Case |
|---------|--------|----------|
| Databricks Sample Datasets | Built-in (`/databricks-datasets/`) | Quick start |
| Delta Sharing samples | [delta.io/sharing](https://delta.io/sharing/) | Cross-org sharing demo |
| MLflow experiment data | Built-in | ML lifecycle demo |
| Unity Catalog samples | Built-in (`samples` catalog) | Governance demo |

### Snowflake

| Dataset | Source | Use Case |
|---------|--------|----------|
| Snowflake Sample Data | Built-in (`SNOWFLAKE_SAMPLE_DATA`) | Quick start |
| Snowflake Marketplace | [marketplace.snowflake.com](https://app.snowflake.com/marketplace) | Industry data |
| Cortex AI samples | Built-in | AI function demo |
| Weather Source | Marketplace (free) | Time-series demo |

### AWS

| Dataset | Source | Use Case |
|---------|--------|----------|
| Registry of Open Data | [registry.opendata.aws](https://registry.opendata.aws/) | All industries |
| AWS Data Exchange | [aws.amazon.com/data-exchange](https://aws.amazon.com/data-exchange/) | Commercial data |
| SageMaker Sample Notebooks | Built-in | ML demo |
| Bedrock Knowledge Base samples | Documentation | RAG demo |

## Quick Setup: Generate Demo Data

```bash
# Generate sample unstructured files for demo
python generate-sample-data.py \
  --industry manufacturing \
  --output-dir /tmp/demo-data \
  --file-count 50

# Upload to FSx for ONTAP S3 AP
aws s3 sync /tmp/demo-data/ s3://<AP_ALIAS>/demo-data/ --region ap-northeast-1
```

## Licensing Notes

- All referenced datasets have open or research licenses
- Verify license terms before using in customer-facing demos
- For customer PoC: use customer's own data (most convincing)
- For internal demos: use CC0/Public Domain datasets only
