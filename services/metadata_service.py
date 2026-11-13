import os
import json
from config import BASE_DIR, Config

try:
    from services.tmdb_service import tmdb_service, GENRE_MAP, GENRE_NAME_TO_ID
except (ImportError, ModuleNotFoundError):
    from tmdb_service import tmdb_service, GENRE_MAP, GENRE_NAME_TO_ID

try:
    from database.models import db_session, GenreOverride
except (ImportError, ModuleNotFoundError):
    try:
        from models import db_session, GenreOverride
    except Exception:
        db_session = None
        GenreOverride = None

OVERRIDE_FILE = os.path.join(BASE_DIR, 'data', 'genre_overrides.json')
if not os.path.exists(OVERRIDE_FILE):
    alt_file = os.path.join(BASE_DIR, 'genre_overrides.json')
    if os.path.exists(alt_file):
        OVERRIDE_FILE = alt_file

class MetadataVerificationService:
    """
    Manages and verifies movie metadata across official TMDB API, curated world cinema registry,
    and user manual corrections.

    Strict Precedence Order:
    1. User Manual Override (highest priority - preserved in JSON file and DB)
    2. Verified Curated Registry (WORLD_CINEMA_REGISTRY)
    3. Official TMDB API metadata
    4. Dataset metadata (tmdb_5000_movies / processed_movies)
    """

    @classmethod
    def get_overrides(cls):
        """Loads manual genre overrides from JSON and database."""
        overrides = {}
        # 1. From JSON file
        if os.path.exists(OVERRIDE_FILE):
            try:
                with open(OVERRIDE_FILE, 'r', encoding='utf-8') as f:
                    overrides = json.load(f)
            except Exception as e:
                print(f"[-] Error reading genre overrides file: {e}")

        # 2. From Database (overrides file if present)
        try:
            db_records = db_session.query(GenreOverride).all()
            for rec in db_records:
                overrides[str(rec.movie_id)] = {
                    'movie_id': rec.movie_id,
                    'title': rec.movie_title,
                    'genres': rec.get_genres(),
                    'genres_str': rec.genres_str,
                    'genre_ids': [GENRE_NAME_TO_ID.get(g.lower(), 28) for g in rec.get_genres()],
                    'notes': rec.notes,
                    'source': 'manual_override'
                }
        except Exception:
            pass

        return overrides

    @classmethod
    def save_override(cls, movie_id, title, genres, notes=None):
        """Saves a user manual genre correction into both JSON and SQLite."""
        if isinstance(genres, str):
            genres_list = [g.strip() for g in genres.split(',') if g.strip()]
        else:
            genres_list = list(genres)

        genres_str = ", ".join(genres_list)
        genre_ids = [GENRE_NAME_TO_ID.get(g.lower(), 28) for g in genres_list]

        # 1. Save to JSON file
        overrides = {}
        if os.path.exists(OVERRIDE_FILE):
            try:
                with open(OVERRIDE_FILE, 'r', encoding='utf-8') as f:
                    overrides = json.load(f)
            except Exception:
                overrides = {}

        overrides[str(movie_id)] = {
            'movie_id': int(movie_id),
            'title': str(title),
            'genres': genres_list,
            'genres_str': genres_str,
            'genre_ids': genre_ids,
            'notes': notes or "User manual correction",
            'source': 'manual_override'
        }

        try:
            os.makedirs(os.path.dirname(OVERRIDE_FILE), exist_ok=True)
            with open(OVERRIDE_FILE, 'w', encoding='utf-8') as f:
                json.dump(overrides, f, indent=2)
        except Exception as e:
            print(f"[-] Could not write to genre overrides file: {e}")

        # 2. Save to Database
        try:
            rec = db_session.query(GenreOverride).filter_by(movie_id=int(movie_id)).first()
            if not rec:
                rec = GenreOverride(
                    movie_id=int(movie_id),
                    movie_title=str(title),
                    genres_json=json.dumps(genres_list),
                    genres_str=genres_str,
                    notes=notes or "User manual correction"
                )
                db_session.add(rec)
            else:
                rec.movie_title = str(title)
                rec.set_genres(genres_list)
                rec.notes = notes or rec.notes
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            print(f"[-] Could not save override to database: {e}")

        return overrides[str(movie_id)]

    @classmethod
    def verify_movie_metadata(cls, movie_id, dataset_movie=None, title=None, raw_genres=None):
        """
        Retrieves and verifies movie metadata:
        1. Checks manual overrides.
        2. Retrieves official TMDB metadata (genres, keywords, credits).
        3. Compares with dataset metadata and detects mismatches.
        4. Returns verified metadata with transparent provenance.
        """
        movie_id_str = str(movie_id).strip()
        overrides = cls.get_overrides()

        # 1. Check user manual override first
        if movie_id_str in overrides:
            ov = overrides[movie_id_str]
            return {
                'id': int(movie_id) if str(movie_id).isdigit() else movie_id,
                'title': ov.get('title') or title or 'Movie',
                'genres': ov.get('genres', []),
                'genre_ids': ov.get('genre_ids', []),
                'genres_str': ov.get('genres_str', ''),
                'source': 'manual_override',
                'source_label': 'User Manual Correction',
                'metadata_source': 'User Manual Correction',
                'has_override': True,
                'is_manual_override': True,
                'notes': ov.get('notes', 'User preserved genre classification'),
                'tmdb_genres': [],
                'dataset_genres': (dataset_movie.get('genres') if dataset_movie else (raw_genres or [])),
                'has_mismatch': False,
                'mismatches_detected': []
            }

        # 2. Check Curated World Cinema Registry
        from ml.world_cinema import WORLD_CINEMA_BY_ID, WORLD_CINEMA_BY_TITLE
        curated = None
        if str(movie_id).isdigit() and int(movie_id) in WORLD_CINEMA_BY_ID:
            curated = WORLD_CINEMA_BY_ID[int(movie_id)]
        elif title and str(title).strip().lower() in WORLD_CINEMA_BY_TITLE:
            curated = WORLD_CINEMA_BY_TITLE[str(title).strip().lower()]

        # 3. Query Official TMDB API
        tmdb_data = None
        if str(movie_id).isdigit():
            tmdb_data = tmdb_service.get_details(int(movie_id))

        tmdb_genres = []
        tmdb_genre_ids = []
        if tmdb_data and tmdb_data.get('genres'):
            tmdb_genres = tmdb_data.get('genres', [])
            tmdb_genre_ids = tmdb_data.get('genre_ids', [])

        dataset_genres = []
        if dataset_movie:
            g = dataset_movie.get('genres')
            if isinstance(g, list):
                dataset_genres = g
            elif isinstance(g, str):
                dataset_genres = [x.strip() for x in g.split(',') if x.strip()]
        elif raw_genres:
            if isinstance(raw_genres, list):
                dataset_genres = raw_genres
            elif isinstance(raw_genres, str):
                dataset_genres = [x.strip() for x in raw_genres.split(',') if x.strip()]

        # Determine best source
        # Note: If TMDB returns empty genres (like for Sita Ramam 982532), prefer curated registry!
        if curated and curated.get('genres'):
            verified_genres = curated.get('genres', [])
            verified_genre_ids = curated.get('genre_ids', [])
            source = 'curated_verified'
            source_label = 'Curated World Cinema Registry'
        elif tmdb_genres and len(tmdb_genres) > 0:
            verified_genres = tmdb_genres
            verified_genre_ids = tmdb_genre_ids
            source = 'tmdb_verified'
            source_label = 'Official TMDB Verified'
        elif dataset_genres:
            verified_genres = dataset_genres
            verified_genre_ids = [GENRE_NAME_TO_ID.get(x.lower(), 28) for x in dataset_genres]
            source = 'dataset_fallback'
            source_label = 'Processed Movie Dataset'
        else:
            verified_genres = ['Drama']
            verified_genre_ids = [18]
            source = 'inferred'
            source_label = 'General Cinema'

        # Check for mismatch between dataset and verified
        has_mismatch = False
        mismatch_notes = ""
        mismatches_detected = []
        if dataset_genres and verified_genres:
            set_d = set([g.lower() for g in dataset_genres])
            set_v = set([g.lower() for g in verified_genres])
            if set_d != set_v:
                has_mismatch = True
                mismatch_notes = f"Dataset had: {', '.join(dataset_genres)} | Verified has: {', '.join(verified_genres)}"
                mismatches_detected.append(mismatch_notes)

        return {
            'id': int(movie_id) if str(movie_id).isdigit() else movie_id,
            'title': (tmdb_data.get('title') if tmdb_data else None) or (curated.get('title') if curated else None) or (dataset_movie.get('title') if dataset_movie else (title or 'Movie')),
            'genres': verified_genres,
            'genre_ids': verified_genre_ids,
            'genres_str': ", ".join(verified_genres),
            'source': source,
            'source_label': source_label,
            'metadata_source': source_label,
            'has_override': False,
            'is_manual_override': False,
            'notes': mismatch_notes or "Verified metadata matching TMDB and curated cinema registry",
            'tmdb_genres': tmdb_genres,
            'dataset_genres': dataset_genres,
            'has_mismatch': has_mismatch,
            'mismatches_detected': mismatches_detected
        }

metadata_service = MetadataVerificationService()
