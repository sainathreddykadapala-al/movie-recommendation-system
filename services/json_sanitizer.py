import math
import numpy as np
import pandas as pd

def sanitize_value(v):
    """Recursively converts NaN, Inf, and non-serializable objects into strict, valid JSON types."""
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        if math.isnan(v) or math.isinf(v):
            return None
        return float(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (np.ndarray, list)):
        return [sanitize_value(x) for x in v]
    if isinstance(v, tuple):
        return [sanitize_value(x) for x in v]
    if isinstance(v, set):
        return [sanitize_value(x) for x in sorted(list(v))]
    if isinstance(v, dict):
        return {str(k): sanitize_value(val) for k, val in v.items()}
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    return v

def sanitize_movie_dict(m):
    """Guarantees a clean, reliable movie object structure for frontend and API responses."""
    if not isinstance(m, dict):
        return {}
    clean = sanitize_value(dict(m))
    
    clean['id'] = int(clean.get('id', 0) or 0)
    clean['title'] = str(clean.get('title') or clean.get('original_title') or 'Untitled')
    clean['release_year'] = str(clean.get('release_year') or '')
    clean['vote_average'] = float(clean.get('vote_average') or 0.0)
    clean['popularity'] = float(clean.get('popularity') or 0.0)
    
    genres = clean.get('genres', [])
    if isinstance(genres, list):
        clean['genres'] = [str(g) for g in genres if g]
        clean['genres_str'] = clean.get('genres_str') or ", ".join(clean['genres'])
    elif isinstance(genres, str):
        clean['genres'] = [g.strip() for g in genres.split(',') if g.strip()]
        clean['genres_str'] = genres
    else:
        clean['genres'] = ['General']
        clean['genres_str'] = 'General'

    clean['overview'] = str(clean.get('overview') or '')
    clean['director'] = str(clean.get('director') or 'Unknown')
    clean['poster_url'] = str(clean.get('poster_url') or '')
    clean['backdrop_url'] = str(clean.get('backdrop_url') or '')
    clean['language_name'] = str(clean.get('language_name') or clean.get('original_language') or 'Global Cinema')
    clean['language_code'] = str(clean.get('language_code') or 'en')
    
    sim_score = float(clean.get('similarity_score') or 0.0)
    clean['similarity_score'] = sim_score
    clean['similarity_percent'] = float(clean.get('similarity_percent') or sim_score)
    clean['explanation'] = str(clean.get('explanation') or '')
    
    return clean

def sanitize_recommendation_response(payload):
    """Sanitizes the entire recommendation API response structure to eliminate all NaN and invalid types."""
    if not isinstance(payload, dict):
        return {'success': False, 'error': 'Invalid payload format', 'recommendations': [], 'count': 0}

    clean_payload = {
        'success': bool(payload.get('success', False)),
        'source': str(payload.get('source', 'global_multi_feature')),
        'source_label': str(payload.get('source_label', 'Multi-Feature Global Recommendation Engine')),
        'available_languages': [str(l) for l in payload.get('available_languages', []) if l],
        'available_genres': [str(g) for g in payload.get('available_genres', []) if g],
        'total_candidates': int(payload.get('total_candidates', 0) or 0),
        'count': int(payload.get('count', 0) or 0)
    }

    if payload.get('error'):
        clean_payload['error'] = str(payload.get('error'))

    if payload.get('selected_movie'):
        clean_payload['selected_movie'] = sanitize_movie_dict(payload['selected_movie'])
        clean_payload['movie'] = clean_payload['selected_movie']  # Provide both keys for compatibility
    else:
        clean_payload['selected_movie'] = None
        clean_payload['movie'] = None

    recs = payload.get('recommendations', [])
    clean_payload['recommendations'] = [sanitize_movie_dict(r) for r in recs if isinstance(r, dict)]
    clean_payload['count'] = len(clean_payload['recommendations'])

    all_recs = payload.get('all_recommendations', [])
    if all_recs:
        clean_payload['all_recommendations'] = [sanitize_movie_dict(r) for r in all_recs if isinstance(r, dict)]
    else:
        clean_payload['all_recommendations'] = clean_payload['recommendations']

    return clean_payload

