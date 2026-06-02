-- =============================================================================
-- Semiconductor — Named Queries
-- Industry: semiconductor
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: gds_layout, oasis_layout, timing_library,
--   drc_report, lvs_report, schematic
-- =============================================================================

-- Name: Designs by Technology Node
-- Description: Inventory of design files grouped by process technology node
SELECT
    technology_node,
    design_stage,
    classification,
    COUNT(*) AS file_count,
    SUM(file_size) AS total_size_bytes,
    MAX(modified_at) AS latest_update
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND technology_node IS NOT NULL
GROUP BY technology_node, design_stage, classification
ORDER BY technology_node, design_stage;

-- Name: Tape-Out Ready Files
-- Description: Find design files at signoff stage approaching tape-out date
SELECT
    file_id,
    file_name,
    technology_node,
    design_stage,
    ip_block,
    cell_library,
    tape_out_date,
    file_size,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND design_stage = 'signoff'
  AND tape_out_date IS NOT NULL
ORDER BY tape_out_date ASC, modified_at DESC;

-- Name: DRC Reports by IP Block
-- Description: Design Rule Check reports for verification tracking
SELECT
    file_id,
    file_name,
    ip_block,
    technology_node,
    cell_library,
    confidence_score,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'drc_report'
ORDER BY ip_block, modified_at DESC;

-- Name: Latest Record per File (Deduplication)
-- Description: Deduplicated view showing only the most recent version of each file
SELECT *
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY file_path
            ORDER BY modified_at DESC
        ) AS row_num
    FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
    WHERE is_deleted = false
) deduped
WHERE row_num = 1
ORDER BY modified_at DESC;
