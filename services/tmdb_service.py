import os
import time
import socket
import requests
from config import Config

# CloudFront IP fallback list for api.themoviedb.org to bypass regional ISP DNS poisoning in certain regions
CLOUDFRONT_IPS = ['13.224.245.92', '13.224.245.44', '13.224.245.47', '13.224.245.63', '99.86.12.53', '3.175.86.103']
_dns_patched = False

def patch_tmdb_dns():
    """
    Patches socket.getaddrinfo to resolve api.themoviedb.org cleanly.
    Tries standard system DNS first. Only falls back to DoH / CloudFront IPs if standard DNS fails.
    """
    global _dns_patched, CLOUDFRONT_IPS
    if _dns_patched:
        return
    try:
        orig_getaddrinfo = socket.getaddrinfo
        def custom_getaddrinfo(host, port, *args, **kwargs):
            if host == 'api.themoviedb.org':
                # Try standard system resolution first
                try:
                    res = orig_getaddrinfo(host, port, *args, **kwargs)
                    if res:
                        return res
                except Exception:
                    pass

                # Fallback to known working IPs if system DNS fails (e.g. ISP blocking)
                for ip in CLOUDFRONT_IPS:
                    try:
                        res = orig_getaddrinfo(ip, port, *args, **kwargs)
                        if res:
                            return res
                    except Exception:
                        continue
            return orig_getaddrinfo(host, port, *args, **kwargs)

        socket.getaddrinfo = custom_getaddrinfo
        _dns_patched = True
    except Exception as e:
        print(f"[-] Could not patch TMDB DNS: {e}")

# Apply DNS patch safely
patch_tmdb_dns()

# Language Mapping (ISO 639-1 code -> display name)
LANGUAGE_MAP = {
    'te': 'Telugu',
    'hi': 'Hindi',
    'ta': 'Tamil',
    'en': 'English',
    'ml': 'Malayalam',
    'kn': 'Kannada',
    'bn': 'Bengali',
    'mr': 'Marathi',
    'pa': 'Punjabi',
    'ko': 'Korean',
    'ja': 'Japanese',
    'zh': 'Chinese',
    'fr': 'French',
    'es': 'Spanish',
    'de': 'German',
    'it': 'Italian',
    'ar': 'Arabic',
    'tr': 'Turkish',
    'ru': 'Russian',
    'pt': 'Portuguese'
}

# Industry to Filter Mapping
INDUSTRY_MAP = {
    'tollywood': {'with_original_language': 'te', 'label': 'Tollywood (Telugu)'},
    'bollywood': {'with_original_language': 'hi', 'label': 'Bollywood (Hindi)'},
    'kollywood': {'with_original_language': 'ta', 'label': 'Kollywood (Tamil)'},
    'mollywood': {'with_original_language': 'ml', 'label': 'Mollywood (Malayalam)'},
    'sandalwood': {'with_original_language': 'kn', 'label': 'Sandalwood (Kannada)'},
    'bengali': {'with_original_language': 'bn', 'label': 'Bengali Cinema'},
    'marathi': {'with_original_language': 'mr', 'label': 'Marathi Cinema'},
    'punjabi': {'with_original_language': 'pa', 'label': 'Punjabi Cinema'},
    'hollywood': {'with_original_language': 'en', 'label': 'Hollywood (USA)'},
    'korean': {'with_original_language': 'ko', 'label': 'Korean Cinema'},
    'japanese': {'with_original_language': 'ja', 'label': 'Japanese Cinema'},
    'chinese': {'with_original_language': 'zh', 'label': 'Chinese Cinema'},
    'french': {'with_original_language': 'fr', 'label': 'French Cinema'},
    'spanish': {'with_original_language': 'es', 'label': 'Spanish Cinema'},
    'anime': {'with_original_language': 'ja', 'with_genres': '16', 'label': 'Anime'},
    'animation': {'with_genres': '16', 'label': 'Animated Movies'},
    'family_animation': {'with_genres': '16,10751', 'label': 'Family Animation'}
}

# Genre ID Mapping
GENRE_MAP = {
    28: 'Action', 12: 'Adventure', 16: 'Animation', 35: 'Comedy',
    80: 'Crime', 99: 'Documentary', 18: 'Drama', 10751: 'Family',
    14: 'Fantasy', 36: 'History', 27: 'Horror', 10402: 'Music',
    9648: 'Mystery', 10749: 'Romance', 878: 'Sci-Fi', 10770: 'TV Movie',
    53: 'Thriller', 10752: 'War', 37: 'Western'
}

# Reverse Genre Mapping (Name -> ID)
GENRE_NAME_TO_ID = {name.lower(): gid for gid, name in GENRE_MAP.items()}
GENRE_NAME_TO_ID.update({
    'science fiction': 878,
    'scifi': 878,
    'sci-fi': 878,
    'romantic': 10749
})

class TMDBService:
    """Service to interact with The Movie Database (TMDB) API v3 with robust caching, fallbacks and multi-language discovery."""

    def __init__(self):
        self.api_key = Config.TMDB_API_KEY
        self.base_url = Config.TMDB_BASE_URL
        self.poster_base = Config.TMDB_IMAGE_BASE_URL
        self.backdrop_base = Config.TMDB_BACKDROP_BASE_URL
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour cache in seconds

        # Reusable session with connection pooling and retries
        from urllib3.util.retry import Retry
        from requests.adapters import HTTPAdapter

        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) CineMatchAI/2.0'
        })

    def _get_cache(self, key):
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['timestamp'] < self.cache_ttl:
                return entry['data']
        return None

    def _set_cache(self, key, data):
        self.cache[key] = {
            'timestamp': time.time(),
            'data': data
        }

    def _make_request(self, endpoint, params=None):
        """Sends authenticated request to TMDB API with circuit-breaker error handling, fast timeout and caching."""
        if not self.api_key or self.api_key == 'YOUR_TMDB_API_KEY_HERE':
            return None

        # Circuit breaker: if network is currently failing, throttled or blocked, return immediately
        if hasattr(self, '_network_offline_until') and time.time() < self._network_offline_until:
            return None

        params = params or {}
        params['api_key'] = self.api_key

        cache_key = f"{endpoint}:{sorted(params.items())}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.get(url, params=params, timeout=1.2)
            if resp.status_code == 200:
                data = resp.json()
                self._set_cache(cache_key, data)
                return data
            elif resp.status_code == 429:
                return None
            else:
                return None
        except Exception as e:
            err_str = str(e)
            # Trip circuit breaker on any network reset, timeout or host unreachable
            if any(k in err_str for k in ["WinError", "10054", "10013", "10061", "Failed to establish", "Max retries", "timeout", "timed out", "ConnectionResetError", "RemoteDisconnected"]):
                self._network_offline_until = time.time() + 60
            return None

    def format_movie(self, item):
        """Standardizes a movie object from TMDB API with rich multi-language metadata."""
        if not item or not isinstance(item, dict):
            return None

        # Build full poster and backdrop URLs
        poster_path = item.get('poster_path')
        backdrop_path = item.get('backdrop_path')

        poster_url = f"{self.poster_base}{poster_path}" if poster_path else None
        backdrop_url = f"{self.backdrop_base}{backdrop_path}" if backdrop_path else None

        # Resolve genres
        genre_ids = item.get('genre_ids', [])
        genre_names = []
        if genre_ids:
            genre_names = [GENRE_MAP.get(gid) for gid in genre_ids if GENRE_MAP.get(gid)]
        elif 'genres' in item and isinstance(item['genres'], list):
            genre_names = [g.get('name') for g in item['genres'] if g.get('name')]
            genre_ids = [g.get('id') for g in item['genres'] if g.get('id')]

        # Resolve release year
        release_date = item.get('release_date', '')
        release_year = release_date[:4] if release_date and len(release_date) >= 4 else 'N/A'

        lang_code = item.get('original_language', 'en')
        lang_name = LANGUAGE_MAP.get(lang_code, lang_code.upper())

        return {
            'id': item.get('id'),
            'title': item.get('title') or item.get('name', 'Untitled'),
            'original_title': item.get('original_title') or item.get('title', ''),
            'overview': item.get('overview', 'No plot summary available.'),
            'release_date': release_date,
            'release_year': release_year,
            'vote_average': round(float(item.get('vote_average', 0.0)), 1),
            'vote_count': item.get('vote_count', 0),
            'popularity': round(float(item.get('popularity', 0.0)), 1),
            'language_code': lang_code,
            'language_name': lang_name,
            'original_language': lang_name,
            'poster_path': poster_path,
            'poster_url': poster_url,
            'backdrop_path': backdrop_path,
            'backdrop_url': backdrop_url,
            'genre_ids': genre_ids,
            'genres': genre_names,
            'genres_str': ", ".join(genre_names) if genre_names else "General",
            'director': item.get('director', 'Unknown'),
            'cast': item.get('cast', []),
            'cast_str': item.get('cast_str', ''),
            'keywords': item.get('keywords', [])
        }

    def format_movie_list(self, raw_list):
        formatted = []
        for m in raw_list:
            fm = self.format_movie(m)
            if fm:
                formatted.append(fm)
        return formatted

    # ----------------------------------------------------
    # API Methods for Cinematic Featured Sections & Home
    # ----------------------------------------------------
    def get_trending(self, time_window='week', page=1):
        """Fetches trending movies of the day or week, with automatic local fallback."""
        data = self._make_request(f"/trending/movie/{time_window}", {'page': page})
        if data and 'results' in data and data['results']:
            return self.format_movie_list(data['results'])
        return self._local_discover(sort_by='popularity.desc', page=page)['results'][:12]

    def get_latest_releases(self, page=1):
        """Fetches now playing and latest released movies, with automatic local fallback."""
        data = self._make_request("/movie/now_playing", {'language': 'en-US', 'page': page})
        if data and 'results' in data and data['results']:
            return self.format_movie_list(data['results'])
        return self._local_discover(period='latest', sort_by='latest', page=page)['results'][:12]

    def get_top_rated(self, page=1):
        """Fetches top-rated movies of all time, with automatic local fallback."""
        data = self._make_request("/movie/top_rated", {'language': 'en-US', 'page': page})
        if data and 'results' in data and data['results']:
            return self.format_movie_list(data['results'])
        return self._local_discover(sort_by='rating', page=page)['results'][:12]

    def get_by_language_and_industry(self, lang_code=None, industry_key=None, page=1):
        """Fetches popular movies by specific language code or film industry, with automatic local fallback."""
        params = {
            'sort_by': 'popularity.desc',
            'page': page,
            'vote_count.gte': 15
        }
        if industry_key and industry_key in INDUSTRY_MAP:
            ind_conf = INDUSTRY_MAP[industry_key]
            for k, v in ind_conf.items():
                if k != 'label':
                    params[k] = v
        elif lang_code:
            params['with_original_language'] = lang_code

        data = self._make_request("/discover/movie", params)
        if data and 'results' in data and data['results']:
            return self.format_movie_list(data['results'])
        return self._local_discover(language=lang_code, industry=industry_key, page=page)['results'][:12]

    def get_classics(self, page=1):
        """Fetches classic movies released before the year 2000, with automatic local fallback."""
        params = {
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 1000,
            'primary_release_date.lte': '1999-12-31',
            'page': page
        }
        data = self._make_request("/discover/movie", params)
        if data and 'results' in data and data['results']:
            return self.format_movie_list(data['results'])
        return self._local_discover(period='classic', sort_by='rating', page=page)['results'][:12]

    def get_anime_and_animation(self, page=1):
        """Fetches animated movies and anime, with automatic local fallback."""
        params = {
            'with_genres': '16',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 50,
            'page': page
        }
        data = self._make_request("/discover/movie", params)
        if data and 'results' in data and data['results']:
            return self.format_movie_list(data['results'])
        return self._local_discover(industry='anime', page=page)['results'][:12]

    # ----------------------------------------------------
    # Multi-Filter Discovery Engine
    # ----------------------------------------------------
    def discover(self, language=None, industry=None, genre_ids=None, period=None, sort_by='popularity.desc', page=1):
        """
        Comprehensive movie discovery combining:
        - Language
        - Industry
        - Multiple Genres
        - Release Period
        - Sort By
        First attempts TMDB API, then seamlessly falls back to local cinema catalog if offline or empty.
        """
        params = {
            'page': page
        }

        # Sorting
        if sort_by == 'rating':
            params['sort_by'] = 'vote_average.desc'
            params['vote_count.gte'] = 50
        elif sort_by == 'latest':
            params['sort_by'] = 'primary_release_date.desc'
        else:
            params['sort_by'] = 'popularity.desc'

        # Industry or Language
        if industry and industry in INDUSTRY_MAP:
            ind_conf = INDUSTRY_MAP[industry]
            for k, v in ind_conf.items():
                if k != 'label':
                    params[k] = v
        elif language:
            params['with_original_language'] = language

        # Multi-genre filter
        if genre_ids:
            if isinstance(genre_ids, list):
                params['with_genres'] = ",".join(str(g) for g in genre_ids)
            else:
                params['with_genres'] = str(genre_ids)

        # Release period filter
        if period == 'classic':
            params['primary_release_date.lte'] = '1999-12-31'
        elif period == '2000-2015':
            params['primary_release_date.gte'] = '2000-01-01'
            params['primary_release_date.lte'] = '2015-12-31'
        elif period == '2016-2024':
            params['primary_release_date.gte'] = '2016-01-01'
            params['primary_release_date.lte'] = '2024-12-31'
        elif period == 'latest':
            params['primary_release_date.gte'] = '2024-01-01'
        elif period and str(period).isdigit():
            params['primary_release_year'] = int(period)

        data = self._make_request("/discover/movie", params)
        if data and 'results' in data and data['results']:
            return {
                'page': data.get('page', 1),
                'total_pages': min(data.get('total_pages', 1), 50),
                'total_results': data.get('total_results', 0),
                'results': self.format_movie_list(data['results'])
            }

        # Fallback to rich local database & World Cinema registry
        return self._local_discover(language=language, industry=industry, genre_ids=genre_ids, period=period, sort_by=sort_by, page=page)

    def _local_discover(self, language=None, industry=None, genre_ids=None, period=None, sort_by='popularity.desc', page=1):
        """
        High-performance local discovery engine querying WORLD_CINEMA_REGISTRY and 4800-movie database.
        Guarantees instant, accurate results regardless of network connectivity or TMDB API restrictions.
        """
        import math
        from ml.world_cinema import WORLD_CINEMA_REGISTRY

        candidates = []
        seen_ids = set()

        # 1. Load curated World Cinema Registry entries
        for m in WORLD_CINEMA_REGISTRY:
            m_copy = dict(m)
            cid = m_copy.get('id')
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                candidates.append(m_copy)

        # 2. Supplement from 4,800 local processed movies
        try:
            from ml.recommendation import MovieRecommender
            recommender = MovieRecommender.get_instance()
            if recommender.is_loaded and recommender.df is not None:
                for _, row in recommender.df.iterrows():
                    cid = int(row.get('id', 0))
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        candidates.append(row.to_dict())
        except Exception:
            pass

        # 3. Determine target language / industry constraint
        target_lang = None
        if industry and industry in INDUSTRY_MAP:
            target_lang = INDUSTRY_MAP[industry].get('with_original_language')
        elif language:
            target_lang = str(language).strip().lower()

        filtered = []
        for c in candidates:
            c_lang = str(c.get('language_code') or c.get('original_language', '')).lower()
            c_ind = str(c.get('industry', '')).lower()

            # Industry/Language filter
            if industry:
                if industry in ['anime', 'animation', 'family_animation']:
                    c_genres = [str(g).lower() for g in c.get('genres', [])]
                    c_gids = [str(gid) for gid in c.get('genre_ids', [])]
                    if 'animation' not in c_genres and '16' not in c_gids:
                        continue
                else:
                    if target_lang and c_lang != target_lang and c_ind != industry:
                        continue
            elif target_lang:
                if c_lang != target_lang:
                    continue

            # Genre filter
            if genre_ids:
                c_genre_ids = [str(gid) for gid in c.get('genre_ids', [])]
                c_genre_names = [str(g).lower() for g in c.get('genres', [])]
                target_g_ids = [str(g) for g in (genre_ids if isinstance(genre_ids, list) else [genre_ids])]

                match = False
                for gid in target_g_ids:
                    if gid in c_genre_ids:
                        match = True
                        break
                    g_name = GENRE_MAP.get(int(gid) if gid.isdigit() else 0, gid).lower()
                    if any(g_name in c_gn for c_gn in c_genre_names):
                        match = True
                        break
                if not match:
                    continue

            # Period filter
            rel_year = int(c.get('release_year', 0) or 0)
            if period == 'latest':
                if rel_year < 2021:
                    continue
            elif period == '2016-2024':
                if not (2016 <= rel_year <= 2024):
                    continue
            elif period == '2000-2015':
                if not (2000 <= rel_year <= 2015):
                    continue
            elif period == 'classic':
                if rel_year > 1999:
                    continue
            elif period and str(period).isdigit():
                if rel_year != int(period):
                    continue

            filtered.append(c)

        # Smart relaxation: if strict period filter left 0 items for this industry/language, relax period
        if not filtered and (language or industry):
            for c in candidates:
                c_lang = str(c.get('language_code') or c.get('original_language', '')).lower()
                c_ind = str(c.get('industry', '')).lower()
                if (target_lang and c_lang == target_lang) or (industry and c_ind == industry):
                    filtered.append(c)

        # 4. Sorting
        if sort_by in ['latest', 'primary_release_date.desc']:
            filtered.sort(key=lambda x: (int(x.get('release_year', 0) or 0), float(x.get('popularity', 0) or 0)), reverse=True)
        elif sort_by in ['rating', 'vote_average.desc']:
            filtered.sort(key=lambda x: (float(x.get('vote_average', 0) or 0), float(x.get('popularity', 0) or 0)), reverse=True)
        else:
            filtered.sort(key=lambda x: float(x.get('popularity', 0) or 0), reverse=True)

        total_results = len(filtered)
        page_size = 20
        total_pages = max(1, math.ceil(total_results / page_size))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_candidates = filtered[start_idx:end_idx]

        formatted_results = [self.enrich_movie(dict(m)) for m in paged_candidates]

        return {
            'page': page,
            'total_pages': total_pages,
            'total_results': total_results,
            'results': formatted_results
        }

    # ----------------------------------------------------
    # Search, Details & Similar Movies
    # ----------------------------------------------------
    def search(self, query, page=1):
        """Searches movies by title or original title with automatic local fallback."""
        if not query or len(str(query).strip()) < 1:
            return []
        data = self._make_request("/search/movie", {
            'query': str(query).strip(),
            'page': page,
            'include_adult': False
        })
        if data and 'results' in data and data['results']:
            return self.format_movie_list(data['results'])
        return self._local_search(query, page=page)

    def _local_search(self, query, page=1):
        """Searches local World Cinema registry and local processed movies."""
        from ml.world_cinema import WORLD_CINEMA_REGISTRY
        q = str(query).strip().lower()
        matches = []
        seen = set()

        for m in WORLD_CINEMA_REGISTRY:
            m_title = str(m.get('title', '')).lower()
            m_orig = str(m.get('original_title', '')).lower()
            if q in m_title or q in m_orig:
                if m['id'] not in seen:
                    seen.add(m['id'])
                    matches.append(self.enrich_movie(dict(m)))

        try:
            from ml.recommendation import MovieRecommender
            recommender = MovieRecommender.get_instance()
            if recommender.is_loaded and recommender.df is not None:
                sub = recommender.df[recommender.df['title'].str.lower().str.contains(q, na=False)].head(15)
                for _, row in sub.iterrows():
                    cid = int(row.get('id', 0))
                    if cid and cid not in seen:
                        seen.add(cid)
                        matches.append(self.enrich_movie(row.to_dict()))
        except Exception:
            pass

        return matches[:15]

    def get_details(self, movie_id):
        """Fetches full movie details including credits (cast, director), keywords, and recommendations."""
        data = self._make_request(f"/movie/{movie_id}", {
            'append_to_response': 'credits,similar,keywords,recommendations'
        })
        if not data:
            return self._local_get_details(movie_id)

        formatted = self.format_movie(data)

        # Extract runtime
        formatted['runtime'] = data.get('runtime', 120) or 120

        # Extract Director and top cast from credits
        director = "Unknown"
        cast_list = []
        if 'credits' in data:
            crew = data['credits'].get('crew', [])
            for c in crew:
                if c.get('job') == 'Director':
                    director = c.get('name', 'Unknown')
                    break
            cast = data['credits'].get('cast', [])
            cast_list = [member.get('name') for member in cast[:6] if member.get('name')]

        formatted['director'] = director
        formatted['cast'] = cast_list
        formatted['cast_str'] = ", ".join(cast_list) if cast_list else "Not listed"

        # Extract keywords
        keywords_list = []
        if 'keywords' in data:
            raw_kw = data['keywords'].get('keywords') or data['keywords'].get('results') or []
            keywords_list = [k.get('name') for k in raw_kw if k.get('name')]
        formatted['keywords'] = keywords_list

        # Extract Similar Movies & Recommendations
        similar_movies = []
        if 'similar' in data and 'results' in data['similar']:
            similar_movies = self.format_movie_list(data['similar']['results'][:10])
        if 'recommendations' in data and 'results' in data['recommendations']:
            rec_movies = self.format_movie_list(data['recommendations']['results'][:10])
            for r in rec_movies:
                if r['id'] not in [s['id'] for s in similar_movies]:
                    similar_movies.append(r)
        formatted['similar_movies'] = similar_movies
        return formatted

    def _local_get_details(self, movie_id):
        """Fallback movie detail resolver using local World Cinema registry and 4800-movie dataset."""
        from ml.world_cinema import WORLD_CINEMA_BY_ID
        if movie_id in WORLD_CINEMA_BY_ID:
            return self.enrich_movie(dict(WORLD_CINEMA_BY_ID[movie_id]))

        try:
            from ml.recommendation import MovieRecommender
            recommender = MovieRecommender.get_instance()
            local_m = recommender.get_movie_by_id(movie_id)
            if local_m:
                return self.enrich_movie(dict(local_m))
        except Exception:
            pass
        return None

    def get_similar(self, movie_id, limit=10):
        """Fetches API-based similar movies from TMDB."""
        data = self._make_request(f"/movie/{movie_id}/similar")
        if data and 'results' in data:
            return self.format_movie_list(data['results'][:limit])
        return []

    def get_cross_language_candidates(self, target_movie, limit_per_lang=4):
        """
        Fast, production-grade candidate retrieval across ALL major languages and industries:
        Telugu, Hindi, Tamil, Malayalam, Kannada, Korean, Japanese, English, Spanish, French.
        Avoids slow blocking sequential calls by combining:
        1. TMDB's direct graph recommendations & similar films (from get_details)
        2. Verified multi-language World Cinema registry (immediate zero-latency)
        3. A single targeted global TMDB discover query matching target genres (under 400ms)
        """
        candidates = []
        seen_ids = set()
        
        target_id = target_movie.get('id')
        if target_id:
            seen_ids.add(int(target_id))

        # 1. First, include TMDB's direct similar & recommendation results if available
        if target_id:
            details_sim = target_movie.get('similar_movies')
            if not details_sim:
                details_sim = self.get_similar(target_id, limit=12)
            if details_sim:
                for m in details_sim:
                    m_id = m.get('id')
                    if m_id and m_id not in seen_ids:
                        seen_ids.add(m_id)
                        candidates.append(m)

        # 2. Add cross-language films from World Cinema Registry
        try:
            from ml.world_cinema import WORLD_CINEMA_REGISTRY
            for wc in WORLD_CINEMA_REGISTRY:
                wc_id = wc.get('id')
                if wc_id and wc_id not in seen_ids:
                    seen_ids.add(wc_id)
                    candidates.append(dict(wc))
        except Exception as e:
            print(f"[-] World cinema registry candidate supplement note: {e}")

        # 3. Extract target genre IDs for live global discover
        target_genre_ids = target_movie.get('genre_ids', [])
        if not target_genre_ids:
            genres_list = target_movie.get('genres', [])
            if isinstance(genres_list, str):
                genres_list = [g.strip() for g in genres_list.split(',')]
            for g in genres_list:
                gid = GENRE_NAME_TO_ID.get(str(g).strip().lower())
                if gid and gid not in target_genre_ids:
                    target_genre_ids.append(gid)

        primary_genre = target_genre_ids[0] if target_genre_ids else 28
        genre_param = str(primary_genre)
        if len(target_genre_ids) > 1:
            genre_param = f"{target_genre_ids[0]}|{target_genre_ids[1]}"

        # 4. Make AT MOST ONE fast live global discover call (covering all languages)
        try:
            data = self._make_request("/discover/movie", {
                'with_genres': genre_param,
                'sort_by': 'popularity.desc',
                'vote_count.gte': 50,
                'page': 1
            })
            if data and 'results' in data:
                formatted = self.format_movie_list(data['results'])
                for m in formatted:
                    m_id = m.get('id')
                    if m_id and m_id not in seen_ids:
                        seen_ids.add(m_id)
                        candidates.append(m)
        except Exception as e:
            print(f"[-] Live discover supplement error: {e}")

        return candidates

    def enrich_movie(self, movie_dict):
        """Enriches a movie dict with live TMDB poster, backdrop, language and details."""
        if not movie_dict or not isinstance(movie_dict, dict):
            return movie_dict

        movie_id = movie_dict.get('id')
        if not movie_id:
            return movie_dict

        # Ensure language name is populated
        lang_code = movie_dict.get('language_code') or movie_dict.get('original_language', 'en')
        if lang_code in LANGUAGE_MAP:
            movie_dict['language_code'] = lang_code
            movie_dict['language_name'] = LANGUAGE_MAP[lang_code]
            movie_dict['original_language'] = LANGUAGE_MAP[lang_code]
        elif not movie_dict.get('language_name'):
            movie_dict['language_code'] = str(lang_code).lower()[:2]
            movie_dict['language_name'] = LANGUAGE_MAP.get(movie_dict['language_code'], str(lang_code).title())
            movie_dict['original_language'] = movie_dict['language_name']

        # If already has full poster_url, return
        if movie_dict.get('poster_url'):
            return movie_dict

        details = self._make_request(f"/movie/{movie_id}")
        if details:
            poster_path = details.get('poster_path')
            backdrop_path = details.get('backdrop_path')
            movie_dict['poster_path'] = poster_path
            movie_dict['backdrop_path'] = backdrop_path
            movie_dict['poster_url'] = f"{self.poster_base}{poster_path}" if poster_path else None
            movie_dict['backdrop_url'] = f"{self.backdrop_base}{backdrop_path}" if backdrop_path else None
            if not movie_dict.get('overview') or movie_dict['overview'] == 'No plot summary available.':
                movie_dict['overview'] = details.get('overview', '')
            if 'original_language' in details and details['original_language'] in LANGUAGE_MAP:
                movie_dict['language_code'] = details['original_language']
                movie_dict['language_name'] = LANGUAGE_MAP[details['original_language']]
                movie_dict['original_language'] = movie_dict['language_name']
        return movie_dict

# Singleton instance
tmdb_service = TMDBService()
