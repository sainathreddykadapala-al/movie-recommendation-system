import os
import time
import socket
import requests
from config import Config

# CloudFront IP fallback list for api.themoviedb.org to bypass regional ISP DNS poisoning
CLOUDFRONT_IPS = ['13.224.245.92', '13.224.245.44', '13.224.245.47', '13.224.245.63', '3.175.86.103']
_dns_patched = False

def patch_tmdb_dns():
    """Patches socket.getaddrinfo to resolve api.themoviedb.org using DoH or closest CloudFront IPs."""
    global _dns_patched, CLOUDFRONT_IPS
    if _dns_patched:
        return
    try:
        # Try dynamic DoH query once
        try:
            doh_resp = requests.get('https://cloudflare-dns.com/dns-query?name=api.themoviedb.org&type=A', 
                                    headers={'accept': 'application/dns-json'}, timeout=3)
            if doh_resp.status_code == 200:
                answers = [ans['data'] for ans in doh_resp.json().get('Answer', []) if ans.get('type') == 1]
                if answers:
                    CLOUDFRONT_IPS = answers + CLOUDFRONT_IPS
        except Exception:
            pass

        orig_getaddrinfo = socket.getaddrinfo
        def custom_getaddrinfo(host, port, *args, **kwargs):
            if host == 'api.themoviedb.org':
                res = []
                for ip in CLOUDFRONT_IPS:
                    try:
                        res.extend(orig_getaddrinfo(ip, port, *args, **kwargs))
                    except Exception:
                        continue
                if res:
                    return res
            return orig_getaddrinfo(host, port, *args, **kwargs)
        socket.getaddrinfo = custom_getaddrinfo
        _dns_patched = True
    except Exception as e:
        print(f"[-] Could not patch TMDB DNS: {e}")

# Apply DNS patch
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
    'it': 'Italian'
}

# Industry to Filter Mapping
INDUSTRY_MAP = {
    'tollywood': {'with_original_language': 'te', 'region': 'IN', 'label': 'Tollywood (Telugu)'},
    'bollywood': {'with_original_language': 'hi', 'region': 'IN', 'label': 'Bollywood (Hindi)'},
    'kollywood': {'with_original_language': 'ta', 'region': 'IN', 'label': 'Kollywood (Tamil)'},
    'mollywood': {'with_original_language': 'ml', 'region': 'IN', 'label': 'Mollywood (Malayalam)'},
    'sandalwood': {'with_original_language': 'kn', 'region': 'IN', 'label': 'Sandalwood (Kannada)'},
    'bengali': {'with_original_language': 'bn', 'region': 'IN', 'label': 'Bengali Cinema'},
    'marathi': {'with_original_language': 'mr', 'region': 'IN', 'label': 'Marathi Cinema'},
    'punjabi': {'with_original_language': 'pa', 'region': 'IN', 'label': 'Punjabi Cinema'},
    'hollywood': {'with_original_language': 'en', 'with_origin_country': 'US', 'label': 'Hollywood (USA)'},
    'korean': {'with_original_language': 'ko', 'with_origin_country': 'KR', 'label': 'Korean Cinema'},
    'japanese': {'with_original_language': 'ja', 'with_origin_country': 'JP', 'label': 'Japanese Cinema'},
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

class TMDBService:
    """Service to interact with The Movie Database (TMDB) API v3 with caching and fallback."""

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
        """Sends authenticated request to TMDB API with error handling and caching."""
        if not self.api_key or self.api_key == 'YOUR_TMDB_API_KEY_HERE':
            return None

        params = params or {}
        params['api_key'] = self.api_key

        cache_key = f"{endpoint}:{sorted(params.items())}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self._set_cache(cache_key, data)
                return data
            else:
                print(f"[-] TMDB API {endpoint} returned status {resp.status_code}")
                return None
        except Exception as e:
            print(f"[-] TMDB API request error for {endpoint}: {e}")
            return None

    def format_movie(self, item):
        """Standardizes a movie object from TMDB API."""
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
            'poster_path': poster_path,
            'poster_url': poster_url,
            'backdrop_path': backdrop_path,
            'backdrop_url': backdrop_url,
            'genres': genre_names,
            'genres_str': ", ".join(genre_names) if genre_names else "General"
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
        """Fetches trending movies of the day or week."""
        data = self._make_request(f"/trending/movie/{time_window}", {'page': page})
        if data and 'results' in data:
            return self.format_movie_list(data['results'])
        return []

    def get_latest_releases(self, page=1):
        """Fetches now playing and latest released movies."""
        data = self._make_request("/movie/now_playing", {'language': 'en-US', 'page': page})
        if data and 'results' in data:
            return self.format_movie_list(data['results'])
        return []

    def get_top_rated(self, page=1):
        """Fetches top-rated movies of all time."""
        data = self._make_request("/movie/top_rated", {'language': 'en-US', 'page': page})
        if data and 'results' in data:
            return self.format_movie_list(data['results'])
        return []

    def get_by_language_and_industry(self, lang_code=None, industry_key=None, page=1):
        """Fetches popular movies by specific language code or film industry."""
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
        if data and 'results' in data:
            return self.format_movie_list(data['results'])
        return []

    def get_classics(self, page=1):
        """Fetches classic movies released before the year 2000."""
        params = {
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 1000,
            'primary_release_date.lte': '1999-12-31',
            'page': page
        }
        data = self._make_request("/discover/movie", params)
        if data and 'results' in data:
            return self.format_movie_list(data['results'])
        return []

    def get_anime_and_animation(self, page=1):
        """Fetches animated movies and anime."""
        params = {
            'with_genres': '16',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 50,
            'page': page
        }
        data = self._make_request("/discover/movie", params)
        if data and 'results' in data:
            return self.format_movie_list(data['results'])
        return []

    # ----------------------------------------------------
    # Multi-Filter Discovery Engine
    # ----------------------------------------------------
    def discover(self, language=None, industry=None, genre_ids=None, period=None, sort_by='popularity.desc', page=1):
        """
        Comprehensive movie discovery combining:
        - Language
        - Industry
        - Multiple Genres
        - Release Period (Classic, 2000-2015, 2016-2024, Latest 2025+, or Year)
        - Sort By (popularity, rating, release_date)
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
            params['primary_release_date.gte'] = '2025-01-01'
        elif period and period.isdigit():
            params['primary_release_year'] = int(period)

        data = self._make_request("/discover/movie", params)
        if data and 'results' in data:
            return {
                'page': data.get('page', 1),
                'total_pages': min(data.get('total_pages', 1), 50),
                'total_results': data.get('total_results', 0),
                'results': self.format_movie_list(data['results'])
            }
        return {'page': 1, 'total_pages': 1, 'total_results': 0, 'results': []}

    # ----------------------------------------------------
    # Search, Details & Similar Movies
    # ----------------------------------------------------
    def search(self, query, page=1):
        """Searches movies by title or original title."""
        if not query or len(query.strip()) < 1:
            return []
        data = self._make_request("/search/movie", {
            'query': query.strip(),
            'page': page,
            'include_adult': False
        })
        if data and 'results' in data:
            return self.format_movie_list(data['results'])
        return []

    def get_details(self, movie_id):
        """Fetches full movie details including credits (cast, director) and similar movies."""
        data = self._make_request(f"/movie/{movie_id}", {
            'append_to_response': 'credits,similar'
        })
        if not data:
            return None

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

        # Extract Similar Movies
        similar_movies = []
        if 'similar' in data and 'results' in data['similar']:
            similar_movies = self.format_movie_list(data['similar']['results'][:8])
        formatted['similar_movies'] = similar_movies

        return formatted

    def get_similar(self, movie_id, limit=10):
        """Fetches API-based similar movies from TMDB."""
        data = self._make_request(f"/movie/{movie_id}/similar")
        if data and 'results' in data:
            return self.format_movie_list(data['results'][:limit])
        return []

    def enrich_movie(self, movie_dict):
        """Enriches a local movie dict with live TMDB poster and backdrop paths."""
        movie_id = movie_dict.get('id')
        if not movie_id:
            return movie_dict

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
        return movie_dict

# Singleton instance
tmdb_service = TMDBService()
