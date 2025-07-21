import yaml, numpy as np, faiss
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
model = SentenceTransformer(MODEL_NAME)

with open("buckets.yaml") as f:
    config = yaml.safe_load(f)

# Compute embedding centroids
bucket_ids, centroids = [], []
for item in config:
    embeds = model.encode(item["examples"], normalize_embeddings=True)
    centroid = embeds.mean(axis=0)
    bucket_ids.append(item["bucket"])
    centroids.append(centroid)

centroids = np.vstack(centroids).astype("float32")
faiss.normalize_L2(centroids)
index = faiss.IndexFlatIP(centroids.shape[1])   # cosine (after L2-normalise)
index.add(x=np.ascontiguousarray(centroids, dtype=np.float32))

# Save for nightly batch
faiss.write_index(index, "bucket_index.faiss")
np.save("bucket_ids.npy", np.array(bucket_ids))