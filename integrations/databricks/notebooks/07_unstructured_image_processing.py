# Databricks notebook source
# MAGIC %md
# MAGIC # 07 - Unstructured Data: Image Processing on FSxN
# MAGIC
# MAGIC Read, process, and write back image files stored on FSx for NetApp ONTAP
# MAGIC via S3 Access Point using Databricks `binaryFile` format.
# MAGIC
# MAGIC ## Use Cases
# MAGIC - Image metadata extraction (EXIF, dimensions, format)
# MAGIC - Thumbnail generation (resize and write back to FSxN)
# MAGIC - Image classification preparation (for ML pipelines)
# MAGIC
# MAGIC ## Prerequisites
# MAGIC - ML Runtime cluster (includes PIL/Pillow)
# MAGIC - External Location configured (from notebook 01)
# MAGIC - Sample images uploaded to FSxN via NFS/SMB

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

S3_ACCESS_POINT_ALIAS = "<your-s3ap-alias>"  # From CloudFormation output
IMAGE_INPUT_PATH = f"s3://{S3_ACCESS_POINT_ALIAS}/media/images/"
THUMBNAIL_OUTPUT_PATH = f"s3://{S3_ACCESS_POINT_ALIAS}/media/thumbnails/"
METADATA_OUTPUT_PATH = f"s3://{S3_ACCESS_POINT_ALIAS}/silver/image_metadata/"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Read Images as Binary Files

# COMMAND ----------

# Read all image files from FSxN via S3 AP
images_df = spark.read.format("binaryFile") \
    .option("pathGlobFilter", "*.{jpg,jpeg,png,tiff,bmp}") \
    .option("recursiveFileLookup", "true") \
    .load(IMAGE_INPUT_PATH)

print(f"Found {images_df.count()} image files")
images_df.select("path", "length", "modificationTime").show(10, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Extract Image Metadata

# COMMAND ----------

from pyspark.sql.functions import udf, col, lit, current_timestamp
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType
from PIL import Image
from io import BytesIO
import json

# Define schema for image metadata
metadata_schema = StructType([
    StructField("width", IntegerType()),
    StructField("height", IntegerType()),
    StructField("format", StringType()),
    StructField("mode", StringType()),
    StructField("has_exif", StringType()),
    StructField("orientation", StringType()),
])

@udf(returnType=metadata_schema)
def extract_image_metadata(content):
    """Extract metadata from image binary content."""
    try:
        img = Image.open(BytesIO(content))
        exif_data = img._getexif() if hasattr(img, '_getexif') else None
        has_exif = "true" if exif_data else "false"
        orientation = str(exif_data.get(274, "unknown")) if exif_data else "unknown"
        return (img.width, img.height, img.format, img.mode, has_exif, orientation)
    except Exception as e:
        return (0, 0, "error", str(e)[:50], "false", "unknown")

# Apply metadata extraction
metadata_df = images_df.withColumn("metadata", extract_image_metadata(col("content"))) \
    .select(
        col("path"),
        col("length").alias("file_size_bytes"),
        col("modificationTime").alias("last_modified"),
        col("metadata.width"),
        col("metadata.height"),
        col("metadata.format").alias("image_format"),
        col("metadata.mode").alias("color_mode"),
        col("metadata.has_exif"),
        col("metadata.orientation"),
        current_timestamp().alias("processed_at")
    )

metadata_df.show(10)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Save Metadata as Delta Table

# COMMAND ----------

# Write image metadata as Delta table on FSxN
metadata_df.write \
    .format("delta") \
    .mode("overwrite") \
    .save(METADATA_OUTPUT_PATH)

# Register as Unity Catalog table
spark.sql(f"""
CREATE TABLE IF NOT EXISTS fsxn_lakehouse.silver.image_metadata
USING DELTA
LOCATION '{METADATA_OUTPUT_PATH}'
COMMENT 'Image metadata extracted from FSxN unstructured files'
""")

print(f"✅ Image metadata saved to: {METADATA_OUTPUT_PATH}")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Query image metadata
# MAGIC SELECT image_format, color_mode, COUNT(*) as count,
# MAGIC        AVG(width) as avg_width, AVG(height) as avg_height,
# MAGIC        SUM(file_size_bytes) / 1024 / 1024 as total_size_mb
# MAGIC FROM fsxn_lakehouse.silver.image_metadata
# MAGIC GROUP BY image_format, color_mode
# MAGIC ORDER BY count DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Generate Thumbnails (Write Back to FSxN)

# COMMAND ----------

from pyspark.sql.functions import pandas_udf
import pandas as pd

THUMBNAIL_SIZE = (256, 256)

@udf(returnType=StringType())
def generate_thumbnail(content, original_path):
    """Generate thumbnail and return output path."""
    try:
        img = Image.open(BytesIO(content))
        img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)

        # Convert to RGB if necessary (for JPEG output)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        # Save to buffer
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        thumbnail_bytes = buffer.getvalue()

        # Determine output filename
        import os
        filename = os.path.basename(original_path)
        name, _ = os.path.splitext(filename)
        output_key = f"thumb_{name}.jpg"

        return output_key
    except Exception as e:
        return f"error: {str(e)[:100]}"

# COMMAND ----------

# Generate thumbnails using Spark UDF
# Note: For actual write-back, use foreachPartition with boto3
from pyspark.sql import Row
import boto3

def write_thumbnails_partition(partition):
    """Write thumbnails back to FSxN via S3 AP."""
    import boto3
    from PIL import Image
    from io import BytesIO
    import os

    s3 = boto3.client('s3', region_name='ap-northeast-1')
    ap_alias = "<your-s3ap-alias>"  # Configure per environment

    for row in partition:
        try:
            img = Image.open(BytesIO(row.content))
            img.thumbnail((256, 256), Image.LANCZOS)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            buffer.seek(0)

            filename = os.path.basename(row.path)
            name, _ = os.path.splitext(filename)
            output_key = f"media/thumbnails/thumb_{name}.jpg"

            s3.put_object(
                Bucket=ap_alias,
                Key=output_key,
                Body=buffer.getvalue(),
                ContentType='image/jpeg'
            )
        except Exception as e:
            print(f"Error processing {row.path}: {e}")

# Execute thumbnail generation
images_df.foreachPartition(write_thumbnails_partition)
print(f"✅ Thumbnails written to: {THUMBNAIL_OUTPUT_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Verify Thumbnails on FSxN

# COMMAND ----------

# List generated thumbnails
thumbnails = dbutils.fs.ls(THUMBNAIL_OUTPUT_PATH)
print(f"Generated {len(thumbnails)} thumbnails")
for t in thumbnails[:10]:
    print(f"  {t.name} ({t.size} bytes)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Performance Summary
# MAGIC
# MAGIC | Metric | Value |
# MAGIC |--------|-------|
# MAGIC | Images processed | (recorded above) |
# MAGIC | Total input size | (from metadata_df) |
# MAGIC | Metadata extraction time | (measure with %%timeit) |
# MAGIC | Thumbnail generation time | (measure with %%timeit) |
# MAGIC | Output thumbnail count | (from verification) |
# MAGIC
# MAGIC ## ONTAP Value
# MAGIC
# MAGIC - **Deduplication**: Similar images (e.g., burst photos) share storage blocks
# MAGIC - **Snapshot**: Protect original images before batch processing
# MAGIC - **FlexClone**: Create isolated copy for ML experimentation
# MAGIC - **Multi-protocol**: Same images accessible via NFS (photographers) + S3 AP (Databricks)
