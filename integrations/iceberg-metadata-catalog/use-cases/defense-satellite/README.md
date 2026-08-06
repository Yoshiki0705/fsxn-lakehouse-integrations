# Defense / Satellite — Iceberg Metadata Catalog

🌐 English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Satellite imagery discovery across archives | Days to find relevant acquisitions | SQL search by AOI, date, cloud cover, sensor |
| Security classification tracking is manual | Data spill risk | Classification level metadata + access control |
| Multi-temporal analysis requires manual inventory | Missed change detection opportunities | Temporal metadata + same-location queries |

## Key File Types

`.tiff` (GeoTIFF), `.jp2` (JPEG2000), `.ntf` (NITF), `.shp`, `.kml`, `.hdf5` (multispectral)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `geographic_area` — Area of interest identifier
- `acquisition_date` — Satellite pass date
- `sensor_type` — optical, SAR, multispectral, hyperspectral
- `cloud_cover_pct` — Cloud cover percentage (0–100)
- `classification_level` — unclassified, confidential, secret
- `ground_resolution_m` — Ground sample distance in meters

## Quick Start

```bash
# Generate defense/satellite sample data
python use-cases/_shared/sample-data/generate.py --industry defense-satellite --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry defense-satellite

# Or use the main demo with defense-satellite profile
./demo/scripts/run-demo.sh --profile defense-satellite
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find clear optical imagery for an area of interest
SELECT file_name, acquisition_date, sensor_type, cloud_cover_pct, ground_resolution_m
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE geographic_area = 'AOI-7'
  AND cloud_cover_pct < 10
  AND sensor_type = 'optical'
  AND classification_level = 'unclassified'
ORDER BY acquisition_date DESC;
```

## Compliance

| Regulation | How addressed |
|-----------|---------------|
| Security classification (UNCLASSIFIED–SECRET) | Classification level metadata + Lake Formation RBAC |
| Data residency requirements | Single-region deployment, no cross-border transfer |

## Related

- [Industry Use Cases — Defense / Satellite](../../docs/industry-use-cases.md#defense--satellite)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC15](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC15-defense-satellite)
