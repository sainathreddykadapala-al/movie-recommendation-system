import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load environment variables from .env file if present
load_dotenv(os.path.join(BASE_DIR, '.env'))

class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'movie-rec-secret-key-2026-academic-prod')
    
    # TMDB API Configuration
    TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '8265bd1679663a7ea12ac168da84d2e8')
    TMDB_BASE_URL = "https://api.themoviedb.org/3"
    TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
    TMDB_BACKDROP_BASE_URL = "https://image.tmdb.org/t/p/original"
    
    # Database
    if os.environ.get('VERCEL'):
        import shutil
        DATABASE_PATH = '/tmp/movie_recommender.db'
        orig_db = os.path.join(BASE_DIR, 'database', 'movie_recommender.db')
        if os.path.exists(orig_db) and not os.path.exists(DATABASE_PATH):
            try:
                shutil.copy2(orig_db, DATABASE_PATH)
            except Exception:
                pass
    else:
        DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'movie_recommender.db')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
    
    # Dataset and model paths
    RAW_MOVIES_PATH = os.path.join(BASE_DIR, 'data', 'raw', 'tmdb_5000_movies.csv')
    RAW_CREDITS_PATH = os.path.join(BASE_DIR, 'data', 'raw', 'tmdb_5000_credits.csv')
    PROCESSED_DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'movies_processed.csv')
    
    MODELS_DIR = os.path.join(BASE_DIR, 'models')
    TFIDF_MODEL_PATH = os.path.join(MODELS_DIR, 'tfidf_vectorizer.pkl')
    KMEANS_MODEL_PATH = os.path.join(MODELS_DIR, 'kmeans_model.pkl')
    TFIDF_MATRIX_PATH = os.path.join(MODELS_DIR, 'tfidf_matrix.pkl')
    PROCESSED_DF_PATH = os.path.join(MODELS_DIR, 'movies_df.pkl')
    
    # Recommendation defaults
    NUM_CLUSTERS = 12
    TOP_N_RECOMMENDATIONS = 10
