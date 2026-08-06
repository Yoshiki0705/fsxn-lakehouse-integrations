# Smart City / Geospatial — Iceberg Metadata Catalog

🌐 English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| GIS data scattered across departments | Duplicate surveys, inconsistent basemaps | Unified catalog with coordinate system metadata |
| Urban planning document discovery is slow | Delayed permit decisions | AI classification + district-level queries |
| Disaster risk data not cross-referenced | Inadequate emergency response planning | Multi-layer geospatial metadata linking |

## Key File Types

`.shp` (Shapefile), `.geojson`, `.tiff` (DEM/DSM), `.las` (LiDAR point cloud), `.pdf` (planning docs), `.gml`

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `data_layer` — parcels, utilities, zoning, elevation, transport
- `coordinate_system` — EPSG code (e.g., EPSG:4326, EPSG:6677)
- `district` — Administrative district or ward
- `spatial_resolution_m` — Spatial resolution in meters
- `last_updated` — Date of last data update
- `data_provider` — Source agency or department

## Quick Start

```bash
# Generate smart city sample data
python use-cases/_shared/sample-data/generate.py --industry smart-city --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry smart-city

# Or use the main demo with smart-city profile
./demo/scripts/run-demo.sh --profile smart-city
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find zoning maps for a specific district
SELECT file_name, data_layer, coordinate_system, last_updated, data_provider
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'zoning_map'
  AND district = 'Central'
  AND last_updated >= '2025-01-01'
ORDER BY last_updated DESC;
```

## Related

- [Industry Use Cases — Smart City](../../docs/industry-use-cases.md#smart-city--geospatial)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC17](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC17-smart-city-geospatial)
