import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"  # Use the same model as for centroids
THRESHOLD = 0.6  # Cosine similarity threshold for classification

def classify_json_entries(
    json_path="screen_captures_ocr.json",
    bucket_ids_path="bucket_ids.npy",
    faiss_index_path="bucket_index.faiss",
    model_name=MODEL_NAME,
    threshold=THRESHOLD
):
    # Load data
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    bucket_ids = np.load(bucket_ids_path)
    index = faiss.read_index(faiss_index_path)
    model = SentenceTransformer(model_name)

    total = len(data)
    for idx, entry in enumerate(data, 1):
        filename = entry.get("filename", "<no filename>")
        print(f"Classifying entry {idx}/{total}: {filename}")
        # Use app_name and full text for embedding
        app_name = entry.get("app_name", "")
        text = entry.get("text_full", "")
        combined = (app_name + " " + text).strip() if app_name else text
        if not combined.strip():
            entry["classification"] = "unclassified"
            print(f"Unclassified (empty text)")
            continue
        emb = model.encode([combined], normalize_embeddings=True).astype("float32")
        D, I = index.search(emb, 1)  # D: similarity, I: index
        score = D[0][0]
        idx_bucket = I[0][0]
        if score >= threshold and idx_bucket >= 0:
            classification = str(bucket_ids[idx_bucket])
            entry["classification"] = classification
            print(f"Classified as: {classification} (score: {score:.3f}, threshold: {threshold})")
        else:
            entry["classification"] = "unclassified"
            print(f"Unclassified (score: {score:.3f}, threshold: {threshold})")

    # Save updated JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Classification complete. Updated file: {json_path}")

if __name__ == "__main__":
    classify_json_entries() 