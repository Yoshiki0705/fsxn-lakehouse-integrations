# Databricks notebook source
# MAGIC %md
# MAGIC # 09 - ML Embeddings on FSxN (Feature Engineering)
# MAGIC
# MAGIC Generate vector embeddings from images and documents stored on FSxN.
# MAGIC Store embeddings as Delta table for similarity search and ML pipelines.
# MAGIC
# MAGIC ## Use Cases
# MAGIC - Image similarity search (find visually similar images)
# MAGIC - Document semantic search (RAG preparation)
# MAGIC - ML Feature Store with unstructured data features
# MAGIC
# MAGIC ## Prerequisites
# MAGIC - ML Runtime cluster with GPU (for image embeddings) or CPU (for text)
# MAGIC - Notebooks 07 and 08 completed (metadata + text extracted)
# MAGIC - Install: `%pip install sentence-transformers torch torchvision`

# COMMAND ----------

# MAGIC %pip install sentence-transformers torch torchvision

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

S3_ACCESS_POINT_ALIAS = "<your-s3ap-alias>"
IMAGE_PATH = f"s3://{S3_ACCESS_POINT_ALIAS}/media/images/"
IMAGE_EMBEDDINGS_PATH = f"s3://{S3_ACCESS_POINT_ALIAS}/gold/features/image_embeddings/"
TEXT_EMBEDDINGS_PATH = f"s3://{S3_ACCESS_POINT_ALIAS}/gold/features/text_embeddings/"

# Embedding model configuration
IMAGE_MODEL = "openai/clip-vit-base-patch32"  # CLIP for image embeddings
TEXT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # Sentence transformer for text
EMBEDDING_DIM = 512  # CLIP output dimension

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 1: Image Embeddings (CLIP)

# COMMAND ----------

import torch
from torchvision import transforms
from PIL import Image
from io import BytesIO
from pyspark.sql.functions import udf, col, current_timestamp
from pyspark.sql.types import ArrayType, FloatType, StringType
import numpy as np

# Load CLIP model on driver (broadcast to workers)
from transformers import CLIPProcessor, CLIPModel

model_name = IMAGE_MODEL
clip_model = CLIPModel.from_pretrained(model_name)
clip_processor = CLIPProcessor.from_pretrained(model_name)

# Broadcast model to workers
bc_model = spark.sparkContext.broadcast(clip_model)
bc_processor = spark.sparkContext.broadcast(clip_processor)

# COMMAND ----------

@udf(returnType=ArrayType(FloatType()))
def generate_image_embedding(content):
    """Generate CLIP embedding for an image."""
    try:
        model = bc_model.value
        processor = bc_processor.value

        img = Image.open(BytesIO(content)).convert("RGB")
        inputs = processor(images=img, return_tensors="pt")

        with torch.no_grad():
            outputs = model.get_image_features(**inputs)

        # Normalize embedding
        embedding = outputs[0].numpy()
        embedding = embedding / np.linalg.norm(embedding)
        return embedding.tolist()
    except Exception as e:
        return None

# COMMAND ----------

# Read images and generate embeddings
images_df = spark.read.format("binaryFile") \
    .option("pathGlobFilter", "*.{jpg,jpeg,png}") \
    .load(IMAGE_PATH)

image_embeddings_df = images_df \
    .withColumn("embedding", generate_image_embedding(col("content"))) \
    .filter(col("embedding").isNotNull()) \
    .select(
        col("path"),
        col("length").alias("file_size"),
        col("embedding"),
        current_timestamp().alias("generated_at")
    )

print(f"Generated embeddings for {image_embeddings_df.count()} images")

# COMMAND ----------

# Save image embeddings as Delta table
image_embeddings_df.write \
    .format("delta") \
    .mode("overwrite") \
    .save(IMAGE_EMBEDDINGS_PATH)

spark.sql(f"""
CREATE TABLE IF NOT EXISTS fsxn_lakehouse.features.image_embeddings
USING DELTA
LOCATION '{IMAGE_EMBEDDINGS_PATH}'
COMMENT 'CLIP image embeddings from FSxN media files'
TBLPROPERTIES ('purpose' = 'ml_feature_store', 'model' = '{IMAGE_MODEL}')
""")

print(f"✅ Image embeddings saved: {IMAGE_EMBEDDINGS_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 2: Text Embeddings (Sentence Transformers)

# COMMAND ----------

from sentence_transformers import SentenceTransformer

# Load text embedding model
text_model = SentenceTransformer(TEXT_MODEL)
bc_text_model = spark.sparkContext.broadcast(text_model)

@udf(returnType=ArrayType(FloatType()))
def generate_text_embedding(text):
    """Generate sentence embedding for text chunk."""
    try:
        if not text or len(text.strip()) < 10:
            return None
        model = bc_text_model.value
        embedding = model.encode(text[:512])  # Truncate to model max
        return embedding.tolist()
    except Exception as e:
        return None

# COMMAND ----------

# Read document text chunks (from notebook 08)
text_df = spark.read.format("delta").load(
    f"s3://{S3_ACCESS_POINT_ALIAS}/silver/document_text/"
)

# Generate embeddings for document text
from pyspark.sql.functions import explode, monotonically_increasing_id

@udf(returnType=ArrayType(StringType()))
def chunk_text_for_embedding(text, chunk_size=500):
    """Split text into chunks suitable for embedding."""
    if not text:
        return []
    chunks = []
    sentences = text.split('.')
    current_chunk = ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < chunk_size:
            current_chunk += sentence + "."
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = sentence + "."
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    return chunks

# Chunk and embed
chunks_df = text_df \
    .withColumn("chunks", chunk_text_for_embedding(col("full_text"))) \
    .select("path", explode("chunks").alias("chunk")) \
    .withColumn("chunk_id", monotonically_increasing_id())

text_embeddings_df = chunks_df \
    .withColumn("embedding", generate_text_embedding(col("chunk"))) \
    .filter(col("embedding").isNotNull()) \
    .withColumn("generated_at", current_timestamp())

print(f"Generated {text_embeddings_df.count()} text embeddings")

# COMMAND ----------

# Save text embeddings
text_embeddings_df.write \
    .format("delta") \
    .mode("overwrite") \
    .save(TEXT_EMBEDDINGS_PATH)

spark.sql(f"""
CREATE TABLE IF NOT EXISTS fsxn_lakehouse.features.text_embeddings
USING DELTA
LOCATION '{TEXT_EMBEDDINGS_PATH}'
COMMENT 'Sentence embeddings from FSxN documents (for RAG/search)'
TBLPROPERTIES ('purpose' = 'ml_feature_store', 'model' = '{TEXT_MODEL}')
""")

print(f"✅ Text embeddings saved: {TEXT_EMBEDDINGS_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 3: Similarity Search Demo

# COMMAND ----------

from pyspark.sql.functions import array, lit
from pyspark.ml.linalg import Vectors
import numpy as np

def cosine_similarity(vec1, vec2):
    """Compute cosine similarity between two vectors."""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

# Example: Find similar images to the first one
sample = image_embeddings_df.first()
query_embedding = sample.embedding

# Compute similarity with all images
@udf(returnType=FloatType())
def compute_similarity(embedding):
    if embedding is None:
        return 0.0
    return cosine_similarity(query_embedding, embedding)

similar_images = image_embeddings_df \
    .withColumn("similarity", compute_similarity(col("embedding"))) \
    .orderBy(col("similarity").desc()) \
    .select("path", "similarity") \
    .limit(5)

print(f"Top 5 images similar to: {sample.path}")
similar_images.show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## ONTAP Value for ML Embeddings
# MAGIC
# MAGIC | Feature | ML Benefit |
# MAGIC |---------|-----------|
# MAGIC | **FlexClone** | Clone embedding table for A/B model comparison (zero-copy) |
# MAGIC | **Snapshot** | Version embeddings per model iteration (reproducibility) |
# MAGIC | **Deduplication** | Embedding vectors for similar images share storage blocks |
# MAGIC | **FabricPool** | Old embedding versions auto-tier to S3 |
# MAGIC | **Multi-protocol** | NFS (data scientists upload) + S3 AP (Spark processes) |
# MAGIC
# MAGIC ## Feature Store Pattern
# MAGIC
# MAGIC ```
# MAGIC FSxN Volume
# MAGIC ├── /media/images/          ← Source (uploaded via NFS/SMB)
# MAGIC ├── /media/documents/       ← Source (uploaded via NFS/SMB)
# MAGIC ├── /silver/image_metadata/ ← Metadata (Delta table)
# MAGIC ├── /silver/document_text/  ← Extracted text (Delta table)
# MAGIC ├── /gold/features/
# MAGIC │   ├── image_embeddings/   ← CLIP embeddings (Delta table)
# MAGIC │   └── text_embeddings/    ← Sentence embeddings (Delta table)
# MAGIC └── Snapshots:
# MAGIC     ├── snap_model_v1       ← Embeddings for model v1
# MAGIC     └── snap_model_v2       ← Embeddings for model v2
# MAGIC ```
