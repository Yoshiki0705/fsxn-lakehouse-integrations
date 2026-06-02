# Autonomous Driving / ADAS — Iceberg Metadata Catalog

🌐 [日本語](README-ja.md) | English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Finding specific driving scenarios in PB of data | Days of manual search | AI scene classification + multi-sensor indexing |
| Annotation status tracking across datasets | Incomplete training data, model gaps | Annotation status metadata + coverage queries |
| Scenario coverage gaps unknown | Safety validation gaps | Weather/lighting/scene type metadata analytics |

## Key File Types

`.bag` (ROS), `.pcd` (point cloud), `.mp4` (camera), `.json` (annotations), `.csv` (CAN bus), `.bin` (LiDAR)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `scene_type` — highway, urban, intersection, parking, rural
- `weather` — clear, rain, snow, fog, night
- `time_of_day` — day, dusk, dawn, night
- `sensor_type` — camera, lidar, radar, gps_imu
- `annotation_status` — pending, in_progress, reviewed, approved
- `vehicle_id` — Data collection vehicle identifier

## Quick Start

```bash
# Generate autonomous driving sample data
python use-cases/_shared/sample-data/generate.py --industry autonomous-driving --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry autonomous-driving

# Or use the main demo with autonomous-driving profile
./demo/scripts/run-demo.sh --profile autonomous-driving
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find unannotated intersection scenes for labeling priority
SELECT file_name, scene_type, weather, time_of_day, sensor_type
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE scene_type = 'intersection'
  AND annotation_status = 'pending'
  AND weather = 'rain'
ORDER BY modified_at DESC;
```

## Related

- [Industry Use Cases — Autonomous Driving](../../docs/industry-use-cases.md#autonomous-driving--adas)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC9](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC9-autonomous-driving)
