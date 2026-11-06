import os
import sys
import joblib
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Ensure project root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import Config
from ml.feature_engineering import generate_recommendation_explanation

class MovieRecommender:
    """
    Production-grade Movie Recommendation Engine.
    Uses TF-IDF Vectorization, K-Means Clustering, and Cosine Similarity.
    """
    _instance = None

    @classmethod
    def get_instance(cls):
        """Singleton accessor to prevent reloading models on each request."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.is_loaded = False
        self.tfidf = None
        self.kmeans = None
        self.tfidf_matrix = None
        self.df = None
        self.load_models()

    def load_models(self):
        """Loads saved models and processed dataset into memory."""
        try:
            if not os.path.exists(Config.PROCESSED_DF_PATH) or not os.path.exists(Config.TFIDF_MATRIX_PATH):
                print("[!] Pre-trained models not found. Triggering automated training...")
                from ml.train_model import train_and_save_pipeline
                train_and_save_pipeline()

            print("[*] Loading ML models into memory...")
            self.tfidf = joblib.load(Config.TFIDF_MODEL_PATH)
            self.kmeans = joblib.load(Config.KMEANS_MODEL_PATH)
            self.tfidf_matrix = joblib.load(Config.TFIDF_MATRIX_PATH)
            self.df = joblib.load(Config.PROCESSED_DF_PATH)
            self.df.reset_index(drop=True, inplace=True)

            # Model consistency check
            if self.tfidf_matrix.shape[0] != len(self.df):
                print(f"[!] Matrix shape mismatch ({self.tfidf_matrix.shape[0]} vs {len(self.df)}). Re-fitting...")
                from ml.train_model import train_and_save_pipeline
                train_and_save_pipeline()
                self.tfidf = joblib.load(Config.TFIDF_MODEL_PATH)
                self.kmeans = joblib.load(Config.KMEANS_MODEL_PATH)
                self.tfidf_matrix = joblib.load(Config.TFIDF_MATRIX_PATH)
                self.df = joblib.load(Config.PROCESSED_DF_PATH)
                self.df.reset_index(drop=True, inplace=True)

            self.is_loaded = True
            print(f"[SUCCESS] Recommender initialized with {len(self.df)} movies and {Config.NUM_CLUSTERS} clusters.")
        except Exception as e:
            print(f"[-] Error loading models: {e}")
            self.is_loaded = False

    def search_movies(self, query, limit=10):
        """
        Fast autocomplete search for movie titles.
        Returns matching movie titles with ID and release year.
        """
        if not self.is_loaded or not query:
            return []

        query = query.strip().lower()
        # Find prefix matches first, then substring matches
        prefix_matches = self.df[self.df['title'].str.lower().str.startswith(query)]
        substring_matches = self.df[
            (~self.df['title'].str.lower().str.startswith(query)) & 
            (self.df['title'].str.lower().str.contains(query, regex=False))
        ]

        combined = pd.concat([prefix_matches, substring_matches]).head(limit)
        results = []
        for _, row in combined.iterrows():
            results.append({
                'id': int(row['id']),
                'title': row['title'],
                'release_year': int(row['release_year']),
                'vote_average': float(row['vote_average']),
                'genres': row['genres_str']
            })
        return results

    def get_movie_by_id(self, movie_id):
        """Retrieves movie metadata dictionary by movie ID."""
        if not self.is_loaded:
            return None
        matches = self.df[self.df['id'] == int(movie_id)]
        if matches.empty:
            return None
        return matches.iloc[0].to_dict()

    def get_movie_by_title(self, title):
        """Retrieves movie metadata dictionary by exact or case-insensitive title."""
        if not self.is_loaded or not title:
            return None
        clean_title = title.strip().lower()
        matches = self.df[self.df['title'].str.lower() == clean_title]
        if matches.empty:
            # Try fuzzy contains
            matches = self.df[self.df['title'].str.lower().str.contains(clean_title, regex=False)]
        if matches.empty:
            return None
        return matches.iloc[0].to_dict()

    def get_featured_movies(self, limit=8):
        """Retrieves top popular and highly rated movies from the real dataset."""
        if not self.is_loaded:
            return []
        # Filter movies with at least 500 votes for statistical significance
        top_df = self.df[self.df['vote_count'] >= 500].sort_values(
            by=['vote_average', 'popularity'], ascending=[False, False]
        ).head(limit)
        
        movies = []
        for _, row in top_df.iterrows():
            movies.append(row.to_dict())
        return movies

    def recommend(self, query_identifier, query_title=None, top_n=10):
        """
        Recommends top_n similar movies based on the selected movie.
        query_identifier can be a movie ID (int) or title (str).
        query_title optionally provides the movie title for reliable resolution.
        """
        if not self.is_loaded:
            raise RuntimeError("Recommendation model is not loaded.")

        movie_matches = pd.DataFrame()

        # 1. Try matching by integer movie ID
        if query_identifier is not None:
            if isinstance(query_identifier, int) or (isinstance(query_identifier, str) and str(query_identifier).strip().isdigit()):
                movie_matches = self.df[self.df['id'] == int(query_identifier)]

        # 2. If not matched by ID, try matching by title
        candidate_titles = []
        if query_title and str(query_title).strip():
            candidate_titles.append(str(query_title).strip())
        if query_identifier and not (isinstance(query_identifier, str) and str(query_identifier).strip().isdigit()):
            candidate_titles.append(str(query_identifier).strip())

        if movie_matches.empty:
            for title in candidate_titles:
                clean_title = title.strip().lower()
                # Exact title match (case-insensitive)
                matches = self.df[self.df['title'].str.strip().str.lower() == clean_title]
                if not matches.empty:
                    movie_matches = matches
                    break

        if movie_matches.empty:
            for title in candidate_titles:
                clean_title = title.strip().lower()
                # Contains match
                matches = self.df[self.df['title'].str.strip().str.lower().str.contains(clean_title, regex=False)]
                if not matches.empty:
                    movie_matches = matches
                    break

        if movie_matches.empty:
            return {
                'success': False,
                'source': 'machine_learning',
                'error': f"Movie '{query_title or query_identifier}' was not found in the trained dataset.",
                'query_movie': None,
                'selected_movie': None,
                'recommendations': [],
                'count': 0
            }

        query_row = movie_matches.iloc[0]
        query_idx = int(self.df.index.get_loc(query_row.name))
        query_cluster = int(query_row['cluster'])
        query_dict = query_row.to_dict()

        # Query vector from tfidf_matrix
        query_vec = self.tfidf_matrix[query_idx]

        # Compute cosine similarities across all candidate vectors
        cosine_sims = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        # Separate candidates: Strictly exclude the query movie itself
        same_cluster_indices = self.df[
            (self.df['cluster'] == query_cluster) & 
            (self.df.index != query_idx) & 
            (self.df['id'] != int(query_row['id']))
        ].index

        # Sort same-cluster candidates by cosine similarity (highest to lowest)
        same_cluster_scores = [(int(idx), float(cosine_sims[idx])) for idx in same_cluster_indices]
        same_cluster_scores.sort(key=lambda x: x[1], reverse=True)

        selected_candidates = []
        seen_movie_ids = {int(query_row['id'])}

        # Take same-cluster candidates with meaningful similarity
        for idx, score in same_cluster_scores:
            if len(selected_candidates) >= top_n:
                break
            m_id = int(self.df.loc[idx, 'id'])
            if m_id not in seen_movie_ids and score > 0.001:
                selected_candidates.append((idx, score, True))
                seen_movie_ids.add(m_id)

        # If we need more candidates to reach top_n, expand search to other clusters
        if len(selected_candidates) < top_n:
            other_indices = self.df[
                (self.df['cluster'] != query_cluster) & 
                (self.df.index != query_idx) & 
                (self.df['id'] != int(query_row['id']))
            ].index
            other_scores = [(int(idx), float(cosine_sims[idx])) for idx in other_indices]
            other_scores.sort(key=lambda x: x[1], reverse=True)

            for idx, score in other_scores:
                if len(selected_candidates) >= top_n:
                    break
                m_id = int(self.df.loc[idx, 'id'])
                if m_id not in seen_movie_ids:
                    selected_candidates.append((idx, score, False))
                    seen_movie_ids.add(m_id)

        # Build detailed recommendation result list
        recommendations = []
        for idx, score, in_same_cluster in selected_candidates:
            rec_row = self.df.loc[idx]
            rec_dict = rec_row.to_dict()
            
            sim_percentage = round(float(score) * 100, 1)
            explanation = generate_recommendation_explanation(query_dict, rec_dict)
            
            recommendations.append({
                'id': int(rec_row['id']),
                'title': str(rec_row['title']),
                'release_year': int(rec_row['release_year']),
                'vote_average': float(rec_row['vote_average']),
                'vote_count': int(rec_row['vote_count']),
                'runtime': int(rec_row['runtime']) if pd.notna(rec_row['runtime']) else 120,
                'director': str(rec_row['director']),
                'genres': str(rec_row['genres_str']),
                'cast': str(rec_row['cast_str']),
                'overview': str(rec_row['overview']),
                'cluster': int(rec_row['cluster']),
                'in_same_cluster': in_same_cluster,
                'similarity_score': round(float(score), 4),
                'similarity_percent': sim_percentage,
                'similarity_label': f"{sim_percentage}% Similarity",
                'explanation': explanation
            })

        selected_movie_info = {
            'id': int(query_row['id']),
            'title': str(query_row['title']),
            'release_year': int(query_row['release_year']),
            'vote_average': float(query_row['vote_average']),
            'vote_count': int(query_row['vote_count']),
            'runtime': int(query_row['runtime']) if pd.notna(query_row['runtime']) else 120,
            'director': str(query_row['director']),
            'genres': str(query_row['genres_str']),
            'cast': str(query_row['cast_str']),
            'overview': str(query_row['overview']),
            'cluster': query_cluster
        }

        return {
            'success': True,
            'source': 'machine_learning',
            'query_movie': selected_movie_info,
            'selected_movie': selected_movie_info,
            'cluster_used': query_cluster,
            'total_cluster_movies': int((self.df['cluster'] == query_cluster).sum()),
            'recommendations': recommendations,
            'count': len(recommendations)
        }

