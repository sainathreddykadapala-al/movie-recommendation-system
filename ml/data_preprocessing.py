import os
import ast
import json
import pandas as pd
import numpy as np

def parse_json_safely(val):
    """Parses JSON or Python literal safely."""
    if pd.isna(val) or not val:
        return []
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except Exception:
        try:
            return ast.literal_eval(val)
        except Exception:
            return []

def extract_names(json_str, limit=None):
    """Extracts a list of 'name' fields from a list of dicts."""
    items = parse_json_safely(json_str)
    if not isinstance(items, list):
        return []
    names = []
    for item in items:
        if isinstance(item, dict) and 'name' in item:
            names.append(item['name'])
            if limit and len(names) >= limit:
                break
    return names

def extract_director(crew_str):
    """Extracts the Director's name from crew json."""
    crew = parse_json_safely(crew_str)
    if not isinstance(crew, list):
        return "Unknown"
    for member in crew:
        if isinstance(member, dict) and member.get('job') == 'Director':
            return member.get('name', 'Unknown')
    return "Unknown"

def preprocess_dataset(raw_movies_path, raw_credits_path, output_csv_path):
    """
    Loads raw TMDB movies and credits CSVs, cleans attributes, parses nested
    data structures, merges on movie ID, and outputs clean processed CSV.
    """
    print(f"[*] Loading raw data from:\n    {raw_movies_path}\n    {raw_credits_path}")
    
    if not os.path.exists(raw_movies_path) or not os.path.exists(raw_credits_path):
        raise FileNotFoundError("Raw TMDB dataset files not found in data/raw/!")

    movies_df = pd.read_csv(raw_movies_path)
    credits_df = pd.read_csv(raw_credits_path)

    print(f"[*] Raw movies shape: {movies_df.shape}")
    print(f"[*] Raw credits shape: {credits_df.shape}")

    # Merge on movie id
    # In credits_df, the ID column is 'movie_id'
    credits_df.rename(columns={'movie_id': 'id'}, inplace=True)
    
    # Merge movies and credits
    # Keep only necessary credits columns to avoid duplicate title columns
    credits_subset = credits_df[['id', 'cast', 'crew']]
    df = pd.merge(movies_df, credits_subset, on='id', how='inner')
    print(f"[*] Merged shape: {df.shape}")

    # Remove duplicates if any
    df.drop_duplicates(subset=['id'], inplace=True)
    df.drop_duplicates(subset=['title'], inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Fill missing values
    df['overview'] = df['overview'].fillna('')
    df['tagline'] = df['tagline'].fillna('')
    df['release_date'] = df['release_date'].fillna('2000-01-01')
    df['runtime'] = df['runtime'].fillna(df['runtime'].median())
    df['vote_average'] = df['vote_average'].fillna(0.0)
    df['vote_count'] = df['vote_count'].fillna(0)
    df['popularity'] = df['popularity'].fillna(0.0)

    # Extract parsed fields
    print("[*] Parsing JSON fields (genres, keywords, cast, crew/director)...")
    df['genre_list'] = df['genres'].apply(lambda x: extract_names(x))
    df['keyword_list'] = df['keywords'].apply(lambda x: extract_names(x))
    df['cast_list'] = df['cast'].apply(lambda x: extract_names(x, limit=4))
    df['director'] = df['crew'].apply(extract_director)

    # Create display strings
    df['genres_str'] = df['genre_list'].apply(lambda lst: ", ".join(lst) if lst else "Drama")
    df['keywords_str'] = df['keyword_list'].apply(lambda lst: ", ".join(lst) if lst else "")
    df['cast_str'] = df['cast_list'].apply(lambda lst: ", ".join(lst) if lst else "Unknown")

    # Extract release year
    df['release_year'] = pd.to_datetime(df['release_date'], errors='coerce').dt.year
    df['release_year'] = df['release_year'].fillna(2000).astype(int)

    # Select final useful columns
    final_cols = [
        'id', 'title', 'release_year', 'release_date', 'runtime',
        'vote_average', 'vote_count', 'popularity',
        'director', 'genres_str', 'cast_str', 'keywords_str',
        'genre_list', 'keyword_list', 'cast_list',
        'overview', 'tagline'
    ]
    processed_df = df[final_cols].copy()

    # Save to processed CSV
    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    # Save a clean CSV version (convert lists to JSON string for CSV)
    csv_df = processed_df.copy()
    csv_df['genre_list'] = csv_df['genre_list'].apply(json.dumps)
    csv_df['keyword_list'] = csv_df['keyword_list'].apply(json.dumps)
    csv_df['cast_list'] = csv_df['cast_list'].apply(json.dumps)
    csv_df.to_csv(output_csv_path, index=False)

    print(f"[SUCCESS] Preprocessed dataset saved to {output_csv_path} with {len(processed_df)} movies.")
    return processed_df

if __name__ == '__main__':
    from config import Config
    preprocess_dataset(Config.RAW_MOVIES_PATH, Config.RAW_CREDITS_PATH, Config.PROCESSED_DATA_PATH)

