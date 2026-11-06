import re
import pandas as pd

def clean_token(text):
    """Lowercases and removes whitespace/special chars to form distinct tokens."""
    if not text or not isinstance(text, str):
        return ""
    # remove spaces and punctuation to create a single token
    return re.sub(r'[^a-zA-Z0-9]', '', text.lower())

def clean_tokens_list(items):
    """Processes a list of strings into clean single-word tokens."""
    if not items or not isinstance(items, list):
        return []
    return [clean_token(item) for item in items if clean_token(item)]

def clean_overview(text):
    """Cleans overview text while retaining meaningful words."""
    if not text or not isinstance(text, str):
        return ""
    # remove non-alphanumeric except spaces
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
    return " ".join(cleaned.split())

def build_features(df):
    """
    Constructs the composite 'tags' text feature for TF-IDF vectorization.
    Combines:
    - cleaned overview & tagline
    - collapsed genre tokens
    - collapsed keyword tokens
    - collapsed top cast member tokens
    - collapsed director token
    """
    df = df.copy()

    def create_tag(row):
        # Overview and tagline words
        overview_words = clean_overview(row['overview'])
        tagline_words = clean_overview(row['tagline'])

        # Collapsed entity tokens
        genres = " ".join(clean_tokens_list(row['genre_list']))
        keywords = " ".join(clean_tokens_list(row['keyword_list']))
        cast = " ".join(clean_tokens_list(row['cast_list']))
        director = clean_token(row['director'])

        # Double-weight director and primary genres for better thematic alignment
        tags = f"{overview_words} {tagline_words} {genres} {genres} {keywords} {cast} {director} {director}"
        return " ".join(tags.split())

    df['tags'] = df.apply(create_tag, axis=1)
    return df

def generate_recommendation_explanation(movie_a, movie_b):
    """
    Generates a clear explanation for why movie_b was recommended based on movie_a,
    using shared metadata (director, cast, genres, keywords).
    """
    reasons = []

    # Check shared director
    dir_a = movie_a.get('director', '')
    dir_b = movie_b.get('director', '')
    if dir_a and dir_b and dir_a != 'Unknown' and dir_a.lower() == dir_b.lower():
        reasons.append(f"directed by {dir_a}")

    # Check shared cast
    cast_a = set([c.lower() for c in movie_a.get('cast_list', []) if c != 'Unknown'])
    cast_b = set([c.lower() for c in movie_b.get('cast_list', []) if c != 'Unknown'])
    shared_cast = cast_a.intersection(cast_b)
    if shared_cast:
        cast_names = ", ".join([c.title() for c in list(shared_cast)[:2]])
        reasons.append(f"stars {cast_names}")

    # Check shared genres
    genres_a = set([g.lower() for g in movie_a.get('genre_list', [])])
    genres_b = set([g.lower() for g in movie_b.get('genre_list', [])])
    shared_genres = genres_a.intersection(genres_b)
    if shared_genres:
        g_names = ", ".join([g.title() for g in list(shared_genres)[:2]])
        reasons.append(f"shares the {g_names} genre")

    # Check shared keywords
    kw_a = set([k.lower() for k in movie_a.get('keyword_list', [])])
    kw_b = set([k.lower() for k in movie_b.get('keyword_list', [])])
    shared_kw = kw_a.intersection(kw_b)
    if shared_kw:
        k_names = ", ".join(list(shared_kw)[:2])
        reasons.append(f"similar themes ({k_names})")

    if reasons:
        return "Recommended because it " + " and ".join(reasons) + "."
    else:
        return "Recommended based on overall thematic and storyline similarity."

