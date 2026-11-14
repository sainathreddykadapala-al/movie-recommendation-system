from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from database.models import db_session, User, Watchlist, RecommendationHistory
from routes.auth_helper import login_required, get_current_user
from services.tmdb_service import tmdb_service, LANGUAGE_MAP, INDUSTRY_MAP, GENRE_MAP
from ml.recommendation import MovieRecommender

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if session.get('user_id'):
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()

    # User's current watchlist IDs for button states
    user_watchlist_ids = set([w.movie_id for w in db_session.query(Watchlist.movie_id).filter_by(user_id=user.id).all()])

    # Fetch featured cinematic sections from TMDB API with in-memory caching
    trending_movies = tmdb_service.get_trending(time_window='week')
    latest_movies = tmdb_service.get_latest_releases()
    top_rated_movies = tmdb_service.get_top_rated()
    
    # Regional Indian Cinema
    telugu_movies = tmdb_service.get_by_language_and_industry(industry_key='tollywood')
    hindi_movies = tmdb_service.get_by_language_and_industry(industry_key='bollywood')
    tamil_movies = tmdb_service.get_by_language_and_industry(industry_key='kollywood')
    malayalam_movies = tmdb_service.get_by_language_and_industry(industry_key='mollywood')
    
    # International & Specialty Collections
    hollywood_movies = tmdb_service.get_by_language_and_industry(industry_key='hollywood')
    korean_movies = tmdb_service.get_by_language_and_industry(industry_key='korean')
    anime_movies = tmdb_service.get_anime_and_animation()
    classic_movies = tmdb_service.get_classics()

    # Fallback to local dataset if API returns empty for any section
    recommender = MovieRecommender.get_instance()
    if not trending_movies and recommender.is_loaded:
        trending_movies = recommender.get_featured_movies(limit=10)
        trending_movies = [tmdb_service.enrich_movie(m) for m in trending_movies]

    sections = [
        {'id': 'trending', 'title': 'Trending Now', 'icon': 'fa-solid fa-arrow-trend-up', 'movies': trending_movies[:10]},
        {'id': 'latest', 'title': 'Latest Releases', 'icon': 'fa-solid fa-sparkles', 'movies': latest_movies[:10]},
        {'id': 'telugu', 'title': 'Tollywood &bull; Telugu Cinema', 'icon': 'fa-solid fa-film', 'movies': telugu_movies[:10]},
        {'id': 'hindi', 'title': 'Bollywood &bull; Hindi Cinema', 'icon': 'fa-solid fa-masks-theater', 'movies': hindi_movies[:10]},
        {'id': 'tamil', 'title': 'Kollywood &bull; Tamil Cinema', 'icon': 'fa-solid fa-clapperboard', 'movies': tamil_movies[:10]},
        {'id': 'malayalam', 'title': 'Mollywood &bull; Malayalam Cinema', 'icon': 'fa-solid fa-video', 'movies': malayalam_movies[:10]},
        {'id': 'hollywood', 'title': 'Hollywood Collection', 'icon': 'fa-solid fa-globe', 'movies': hollywood_movies[:10]},
        {'id': 'korean', 'title': 'Korean Cinema & K-Dramas', 'icon': 'fa-solid fa-heart', 'movies': korean_movies[:10]},
        {'id': 'anime', 'title': 'Anime & Animated Features', 'icon': 'fa-solid fa-wand-magic-sparkles', 'movies': anime_movies[:10]},
        {'id': 'classics', 'title': 'Classic Masterpieces (Pre-2000)', 'icon': 'fa-solid fa-landmark', 'movies': classic_movies[:10]},
        {'id': 'top_rated', 'title': 'Top Rated of All Time', 'icon': 'fa-solid fa-star', 'movies': top_rated_movies[:10]}
    ]

    return render_template(
        'dashboard.html',
        user=user,
        sections=sections,
        watchlist_ids=user_watchlist_ids,
        languages=LANGUAGE_MAP,
        industries=INDUSTRY_MAP,
        genres=GENRE_MAP
    )

@main_bp.route('/explore')
@login_required
def explore():
    user = get_current_user()
    user_watchlist_ids = set([w.movie_id for w in db_session.query(Watchlist.movie_id).filter_by(user_id=user.id).all()])

    # URL query filters
    language = request.args.get('language', '')
    industry = request.args.get('industry', '')
    genre = request.args.get('genre', '')
    period = request.args.get('period', '')
    sort_by = request.args.get('sort_by', 'popularity.desc')
    page = int(request.args.get('page', 1))

    # Initial discover results
    results = tmdb_service.discover(
        language=language if language else None,
        industry=industry if industry else None,
        genre_ids=[genre] if genre else None,
        period=period if period else None,
        sort_by=sort_by,
        page=page
    )

    return render_template(
        'explore.html',
        user=user,
        movies=results.get('results', []),
        page=results.get('page', 1),
        total_pages=results.get('total_pages', 1),
        total_results=results.get('total_results', 0),
        selected_language=language,
        selected_industry=industry,
        selected_genre=genre,
        selected_period=period,
        selected_sort=sort_by,
        languages=LANGUAGE_MAP,
        industries=INDUSTRY_MAP,
        genres=GENRE_MAP,
        watchlist_ids=user_watchlist_ids
    )

@main_bp.route('/api/discover')
def api_discover():
    language = request.args.get('language', '')
    industry = request.args.get('industry', '')
    genres_param = request.args.get('genres', '')
    period = request.args.get('period', '')
    sort_by = request.args.get('sort_by', 'popularity.desc')
    page = int(request.args.get('page', 1))

    genre_ids = [g.strip() for g in genres_param.split(',') if g.strip()] if genres_param else None

    result = tmdb_service.discover(
        language=language if language else None,
        industry=industry if industry else None,
        genre_ids=genre_ids,
        period=period if period else None,
        sort_by=sort_by,
        page=page
    )

    user = get_current_user()
    watchlist_ids = set([w.movie_id for w in db_session.query(Watchlist.movie_id).filter_by(user_id=user.id).all()]) if user else set()

    from services.json_sanitizer import sanitize_movie_dict
    sanitized_movies = []
    for m in result.get('results', []):
        sm = sanitize_movie_dict(m)
        sm['in_watchlist'] = sm['id'] in watchlist_ids
        sanitized_movies.append(sm)

    return jsonify({
        'success': True,
        'page': result.get('page', 1),
        'total_pages': result.get('total_pages', 1),
        'total_results': result.get('total_results', 0),
        'movies': sanitized_movies
    })

@main_bp.route('/api/search-tmdb')
def api_search_tmdb():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 1:
        return jsonify([])
    results = tmdb_service.search(query, page=1)
    return jsonify(results[:8])

@main_bp.route('/api/movie-details/<int:movie_id>')
def api_movie_details_full(movie_id):
    details = tmdb_service.get_details(movie_id)
    if not details:
        # Fallback to local ML model if offline or not in TMDB API
        recommender = MovieRecommender.get_instance()
        local_movie = recommender.get_movie_by_id(movie_id)
        if local_movie:
            enriched = tmdb_service.enrich_movie(local_movie, fetch_remote=True)
            from services.json_sanitizer import sanitize_movie_dict
            return jsonify({'success': True, 'movie': sanitize_movie_dict(enriched)})
        return jsonify({'success': False, 'error': 'Movie not found'}), 404
    return jsonify({'success': True, 'movie': details})

@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = get_current_user()
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            full_name = request.form.get('full_name', '').strip()
            if not full_name or len(full_name) < 2:
                flash('Please enter a valid full name (at least 2 characters).', 'danger')
            else:
                user.full_name = full_name
                session['user_name'] = full_name
                db_session.commit()
                flash('Profile details updated successfully!', 'success')

        elif action == 'change_password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_new_password = request.form.get('confirm_new_password', '')

            if not current_password or not new_password or not confirm_new_password:
                flash('All password fields are required.', 'danger')
            elif not user.check_password(current_password):
                flash('Current password is incorrect.', 'danger')
            elif len(new_password) < 6:
                flash('New password must be at least 6 characters long.', 'danger')
            elif new_password != confirm_new_password:
                flash('New passwords do not match.', 'danger')
            else:
                user.set_password(new_password)
                db_session.commit()
                flash('Password changed successfully!', 'success')

        return redirect(url_for('main.profile'))

    rec_count = db_session.query(RecommendationHistory).filter_by(user_id=user.id).count()
    watchlist_count = db_session.query(Watchlist).filter_by(user_id=user.id).count()

    return render_template(
        'profile.html',
        user=user,
        rec_count=rec_count,
        watchlist_count=watchlist_count
    )

@main_bp.route('/about')
def about():
    return render_template('about.html')
