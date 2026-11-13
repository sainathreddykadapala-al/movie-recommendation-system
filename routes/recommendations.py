from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session

try:
    from database.models import db_session, RecommendationHistory, Watchlist
except (ImportError, ModuleNotFoundError):
    from models import db_session, RecommendationHistory, Watchlist

try:
    from routes.auth_helper import login_required, get_current_user
except (ImportError, ModuleNotFoundError):
    from auth_helper import login_required, get_current_user

from ml.recommendation import MovieRecommender

try:
    from services.tmdb_service import tmdb_service, LANGUAGE_MAP, GENRE_MAP
except (ImportError, ModuleNotFoundError):
    from tmdb_service import tmdb_service, LANGUAGE_MAP, GENRE_MAP

try:
    from services.metadata_service import metadata_service
except (ImportError, ModuleNotFoundError):
    try:
        from metadata_service import metadata_service
    except Exception:
        metadata_service = None

try:
    from services.json_sanitizer import sanitize_recommendation_response, sanitize_movie_dict
except (ImportError, ModuleNotFoundError):
    try:
        from json_sanitizer import sanitize_recommendation_response, sanitize_movie_dict
    except Exception:
        sanitize_recommendation_response = lambda x: x
        sanitize_movie_dict = lambda x: x

rec_bp = Blueprint('recommendations', __name__)

@rec_bp.route('/api/movies/<int:movie_id>/override-genres', methods=['POST'])
@login_required
def api_override_movie_genres(movie_id):
    """
    Endpoint for users to manually correct a movie's genre classification.
    Saves and preserves the correction in both data/genre_overrides.json and SQLite genre_overrides table.
    """
    data = request.get_json(silent=True) or {}
    genres = data.get('genres', [])
    if isinstance(genres, str):
        genres = [g.strip() for g in genres.split(',') if g.strip()]
    
    title = data.get('title') or f"Movie #{movie_id}"
    notes = data.get('notes') or "User manual genre override"

    if not genres:
        return jsonify({'success': False, 'error': 'At least one genre must be specified.'}), 400

    saved = metadata_service.save_override(movie_id, title, genres, notes=notes)
    if saved:
        return jsonify({
            'success': True,
            'message': f"Genre correction for '{title}' saved successfully.",
            'movie_id': movie_id,
            'genres': genres
        }), 200
    return jsonify({'success': False, 'error': 'Could not save genre override.'}), 500

@rec_bp.route('/recommend', methods=['GET', 'POST'])
@login_required
def recommend():
    recommender = MovieRecommender.get_instance()
    user = get_current_user()

    # Determine movie query from POST form or GET query param
    query = ""
    movie_id_param = request.args.get('movie_id')
    language_filter = request.args.get('language') or request.form.get('language')
    genre_filter = request.args.get('genre') or request.form.get('genre')
    sort_by = request.args.get('sort_by') or request.form.get('sort_by') or 'similarity'

    if request.method == 'POST':
        query = request.form.get('movie_title', '').strip()
    else:
        query = request.args.get('movie', '').strip()

    if not query and not movie_id_param:
        # Show the search & recommend page with popular suggestions
        popular_suggestions = recommender.get_featured_movies(limit=8)
        for s in popular_suggestions:
            tmdb_service.enrich_movie(s)
        return render_template('recommend.html', popular_suggestions=popular_suggestions)

    target_identifier = movie_id_param if movie_id_param else query

    # Run the Global Multi-Language Recommendation Engine
    result = recommender.recommend_global(
        target_identifier,
        query_title=query,
        language_filter=language_filter,
        genre_filter=genre_filter,
        sort_by=sort_by,
        top_n=30
    )

    user_watchlist_ids = set([w.movie_id for w in db_session.query(Watchlist.movie_id).filter_by(user_id=user.id).all()]) if user else set()

    if result.get('success'):
        query_movie = tmdb_service.enrich_movie(result['selected_movie'])
        recommendations = result['recommendations']
        all_recommendations = result.get('all_recommendations', recommendations)

        # Save to user's RecommendationHistory in SQLite
        if user:
            try:
                history_entry = RecommendationHistory(
                    user_id=user.id,
                    selected_movie_id=query_movie.get('id', 0),
                    selected_movie_title=query_movie.get('title', 'Unknown'),
                    cluster_id=query_movie.get('cluster', 0)
                )
                history_entry.set_recommendations(recommendations[:15])
                db_session.add(history_entry)
                db_session.commit()
            except Exception as e:
                db_session.rollback()
                print(f"[-] Could not save recommendation history: {e}")

        return render_template(
            'results.html',
            is_ml=True,
            query_movie=query_movie,
            recommendations=recommendations,
            all_recommendations=all_recommendations,
            available_languages=result.get('available_languages', []),
            available_genres=result.get('available_genres', []),
            current_language_filter=language_filter or 'all',
            current_genre_filter=genre_filter or 'all',
            current_sort_by=sort_by,
            watchlist_ids=user_watchlist_ids,
            languages_map=LANGUAGE_MAP
        )

    flash(f"Could not find recommendations for '{query or target_identifier}'. Please try searching another title or selecting from the catalog.", 'warning')
    popular_suggestions = recommender.get_featured_movies(limit=8)
    for s in popular_suggestions:
        tmdb_service.enrich_movie(s)
    return render_template('recommend.html', popular_suggestions=popular_suggestions)

@rec_bp.route('/history')
@login_required
def history():
    user = get_current_user()
    history_records = db_session.query(RecommendationHistory).filter_by(
        user_id=user.id
    ).order_by(RecommendationHistory.created_at.desc()).all()

    return render_template('history.html', history_records=history_records)

@rec_bp.route('/api/search')
def api_search():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify([])
    
    # First search TMDB for high quality poster thumbnails across world cinema
    tmdb_results = tmdb_service.search(query, page=1)
    if tmdb_results:
        return jsonify([sanitize_movie_dict(m) for m in tmdb_results[:8]])

    # Fallback to local recommender search
    recommender = MovieRecommender.get_instance()
    results = recommender.search_movies(query, limit=8)
    for r in results:
        tmdb_service.enrich_movie(r)
    return jsonify([sanitize_movie_dict(r) for r in results])

@rec_bp.route('/api/movie/<int:movie_id>')
def api_movie_details(movie_id):
    # Try TMDB service first for full backdrop, cast, language and details
    details = tmdb_service.get_details(movie_id)
    if details:
        return jsonify({'success': True, 'movie': sanitize_movie_dict(details)})
    
    recommender = MovieRecommender.get_instance()
    movie = recommender.get_movie_by_id(movie_id)
    if not movie:
        return jsonify({'success': False, 'error': 'Movie not found'}), 404
    enriched = tmdb_service.enrich_movie(movie)
    return jsonify({'success': True, 'movie': sanitize_movie_dict(enriched)})

@rec_bp.route('/api/movies/<movie_id>/similar', methods=['GET', 'POST', 'OPTIONS'])
@rec_bp.route('/api/movies/similar', methods=['GET', 'POST', 'OPTIONS'])
def api_movie_similar(movie_id=None):
    """
    Dedicated JSON API endpoint for cross-language similar movie recommendations.
    Accepts movie ID in URL path or JSON/query params, along with optional filters (language, genre, sort_by).
    Executes the Global Multi-Feature Recommendation Engine (Genre 30%, Overview 30%, Keywords 20%, Cast 5%, Director 5%, Cluster 10%).
    """
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = {}
    if request.is_json:
        data = request.get_json(silent=True) or {}

    # Extract movie_id from param, args, or json body
    if not movie_id:
        movie_id = request.args.get('movie_id') or data.get('movie_id') or data.get('id')

    title = request.args.get('title') or data.get('title') or request.form.get('title')

    if not movie_id or str(movie_id).strip().lower() in ['none', 'null', 'undefined', '']:
        if not title:
            return jsonify({'success': False, 'error': 'A valid movie ID or title must be provided.'}), 400
        movie_id_str = title.strip()
    else:
        movie_id_str = str(movie_id).strip()

    language_filter = request.args.get('language') or data.get('language')
    genre_filter = request.args.get('genre') or data.get('genre')
    sort_by = request.args.get('sort_by') or data.get('sort_by') or 'similarity'

    recommender = MovieRecommender.get_instance()
    user = get_current_user()
    watchlist_ids = set()
    if user:
        watchlist_ids = set([w.movie_id for w in db_session.query(Watchlist.movie_id).filter_by(user_id=user.id).all()])

    try:
        result = recommender.recommend_global(
            movie_id_str,
            query_title=title,
            language_filter=language_filter,
            genre_filter=genre_filter,
            sort_by=sort_by,
            top_n=30
        )

        if result.get('success') and result.get('recommendations'):
            selected_movie = tmdb_service.enrich_movie(result['selected_movie'])
            # Preserve verified metadata provenance in returned payload
            selected_movie['metadata_source'] = result['selected_movie'].get('metadata_source', 'Verified')
            selected_movie['is_manual_override'] = result['selected_movie'].get('is_manual_override', False)
            selected_movie['mismatches_detected'] = result['selected_movie'].get('mismatches_detected', [])

            enriched_recs = []
            for rec in result['recommendations']:
                enriched = tmdb_service.enrich_movie(rec)
                enriched['is_in_watchlist'] = (enriched.get('id') in watchlist_ids)
                enriched_recs.append(enriched)

            # Record in user history if authenticated
            if user:
                try:
                    history_entry = RecommendationHistory(
                        user_id=user.id,
                        selected_movie_id=selected_movie.get('id', 0),
                        selected_movie_title=selected_movie.get('title', 'Unknown'),
                        cluster_id=selected_movie.get('cluster', 0)
                    )
                    history_entry.set_recommendations(enriched_recs[:15])
                    db_session.add(history_entry)
                    db_session.commit()
                except Exception as e:
                    db_session.rollback()

            raw_payload = {
                'success': True,
                'source': 'global_multi_feature',
                'source_label': 'Global Multi-Feature Engine (All Languages)',
                'selected_movie': selected_movie,
                'movie': selected_movie,
                'recommendations': enriched_recs,
                'all_recommendations': result.get('all_recommendations', enriched_recs),
                'available_languages': result.get('available_languages', []),
                'available_genres': result.get('available_genres', []),
                'count': len(enriched_recs),
                'total_candidates': result.get('total_candidates', len(enriched_recs))
            }
            return jsonify(sanitize_recommendation_response(raw_payload)), 200

    except Exception as e:
        print(f"[-] Global recommendation API error for {movie_id_str}: {e}")

    # Fallback if both ML and live discover couldn't resolve
    error_payload = {
        'success': False,
        'error': f"Movie '{title or movie_id_str}' was not found in the global cinema database.",
        'movie': None,
        'selected_movie': None,
        'recommendations': [],
        'count': 0
    }
    return jsonify(sanitize_recommendation_response(error_payload)), 404
