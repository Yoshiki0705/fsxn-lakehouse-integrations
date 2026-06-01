-- pending_enrichment.sql — Files awaiting AI enrichment
SELECT file_id, file_name, file_type, file_size, enrichment_status
FROM metadata.latest_unstructured_files
WHERE enrichment_status = 'pending'
ORDER BY file_size DESC;
