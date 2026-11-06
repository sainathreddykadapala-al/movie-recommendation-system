import os
import sys
import joblib
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

# Add project root to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import Config
from ml.data_preprocessing import preprocess_dataset
from ml.feature_engineering import build_features

def train_and_save_pipeline():
    """
    Executes full ML training pipeline:
    1. Preprocesses raw TMDB dataset
    2. Builds engineered text features
    3. Fits TF-IDF vectorizer (5000 features, English stop words, unigrams+bigrams)
    4. Fits K-Means clustering (K=12)
    5. Saves all artifacts to models/ directory via Joblib
    """
    print("=" * 70)
    print("STARTING MACHINE LEARNING PIPELINE TRAINING")
    print("=" * 70)

    # 1. Dataset Preprocessing
    if not os.path.exists(Config.PROCESSED_DATA_PATH):
        print("[*] Processed dataset not found. Running data preprocessing...")
        df = preprocess_dataset(Config.RAW_MOVIES_PATH, Config.RAW_CREDITS_PATH, Config.PROCESSED_DATA_PATH)
    else:
        print(f"[*] Loading processed dataset from: {Config.PROCESSED_DATA_PATH}")
        df = pd.read_csv(Config.PROCESSED_DATA_PATH)
        import json
        df['genre_list'] = df['genre_list'].apply(lambda x: json.loads(x) if isinstance(x, str) else [])
        df['keyword_list'] = df['keyword_list'].apply(lambda x: json.loads(x) if isinstance(x, str) else [])
        df['cast_list'] = df['cast_list'].apply(lambda x: json.loads(x) if isinstance(x, str) else [])

    df.reset_index(drop=True, inplace=True)
    print(f"[*] Total movies in dataset: {len(df)}")

    # 2. Feature Engineering
    print("[*] Generating combined text features (tags)...")
    df = build_features(df)
    print(f"[*] Sample tags from movie '{df.iloc[0]['title']}':")
    print(f"    {df.iloc[0]['tags'][:150]}...\n")

    # 3. TF-IDF Vectorization
    print("[*] Fitting TfidfVectorizer (max_features=5000, unigrams + bigrams)...")
    tfidf = TfidfVectorizer(
        max_features=5000,
        stop_words='english',
        ngram_range=(1, 2)
    )
    tfidf_matrix = tfidf.fit_transform(df['tags'])
    print(f"[+] TF-IDF Matrix shape: {tfidf_matrix.shape}")

    # 4. K-Means Clustering
    num_clusters = Config.NUM_CLUSTERS
    print(f"[*] Fitting K-Means Clustering (n_clusters={num_clusters}, random_state=42)...")
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(tfidf_matrix)
    df['cluster'] = cluster_labels

    print(f"[+] K-Means Inertia: {kmeans.inertia_:.2f}")
    cluster_counts = df['cluster'].value_counts().sort_index()
    print("[+] Movies distribution across clusters:")
    for cluster_id, count in cluster_counts.items():
        print(f"    Cluster {cluster_id:2d}: {count:4d} movies")

    # Analyze top keywords per cluster for explainability
    print("\n[*] Top 5 representative keywords per cluster:")
    order_centroids = kmeans.cluster_centers_.argsort()[:, ::-1]
    terms = tfidf.get_feature_names_out()
    cluster_keywords = {}
    for i in range(num_clusters):
        top_terms = [terms[ind] for ind in order_centroids[i, :5]]
        cluster_keywords[i] = top_terms
        print(f"    Cluster {i:2d}: {', '.join(top_terms)}")

    # 5. Persist Models and Artifacts
    os.makedirs(Config.MODELS_DIR, exist_ok=True)
    print(f"\n[*] Saving trained models and data structures to: {Config.MODELS_DIR}")
    
    joblib.dump(tfidf, Config.TFIDF_MODEL_PATH)
    print(f"[+] Saved TF-IDF Vectorizer -> {Config.TFIDF_MODEL_PATH}")
    
    joblib.dump(kmeans, Config.KMEANS_MODEL_PATH)
    print(f"[+] Saved K-Means Model -> {Config.KMEANS_MODEL_PATH}")
    
    joblib.dump(tfidf_matrix, Config.TFIDF_MATRIX_PATH)
    print(f"[+] Saved TF-IDF Matrix -> {Config.TFIDF_MATRIX_PATH}")
    
    joblib.dump(df, Config.PROCESSED_DF_PATH)
    print(f"[+] Saved Processed DataFrame -> {Config.PROCESSED_DF_PATH}")

    print("\n" + "=" * 70)
    print("[SUCCESS] Machine Learning Pipeline trained and saved successfully!")
    print("=" * 70)
    return True

if __name__ == '__main__':
    train_and_save_pipeline()

