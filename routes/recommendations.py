from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from database.models import db_session, RecommendationHistory, Watchlist
from routes.auth_helper import login_required, get_current_user
from ml.recommendation import MovieRecommender
from services.tmdb_service import tmdb_service

rec_bp = Blueprint('recommendations', __name__)

@rec_bp.route('/recommend', methods=['GET', 'POST'])
@login_required
def recommend():
    recommender = MovieRecommender.get_instance()
    user = get_current_user()

    # Determine movie query from POST form or GET query param
    query = ""
    movie_id_param = request.args.get('movie_id')

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

    # 1. Attempt Machine Learning Recommendation
    result = recommender.recommend(target_identifier, query_title=query, top_n=10)

    user_watchlist_ids = set([w.movie_id for w in db_session.query(Watchlist.movie_id).filter_by(user_id=user.id).all()]) if user else set()

    if result.get('success'):
        # Enrich query movie and all recommendations with TMDB real posters and backdrops
        query_movie = tmdb_service.enrich_movie(result['query_movie'])
        
        enriched_recommendations = []
        for rec in result['recommendations']:
            enriched = tmdb_service.enrich_movie(rec)
            enriched_recommendations.append(enriched)

        # Save to user's RecommendationHistory in SQLite
        if user:
            try:
                history_entry = RecommendationHistory(
                    user_id=user.id,
                    selected_movie_id=query_movie['id'],
                    selected_movie_title=query_movie['title'],
                    cluster_id=result['cluster_used']
                )
                history_entry.set_recommendations(enriched_recommendations)
                db_session.add(history_entry)
                db_session.commit()
            except Exception as e:
                db_session.rollback()
                print(f"[-] Could not save recommendation history: {e}")

        return render_template(
            'results.html',
            is_ml=True,
            query_movie=query_movie,
            cluster_used=result['cluster_used'],
            total_cluster_movies=result['total_cluster_movies'],
            recommendations=enriched_recommendations,
            watchlist_ids=user_watchlist_ids
        )

    # 2. Movie not in trained dataset: Try TMDB API fallback
    api_movie = None
    if movie_id_param and movie_id_param.isdigit():
        api_movie = tmdb_service.get_details(int(movie_id_param))
    elif query:
        search_res = tmdb_service.search(query)
        if search_res:
            api_movie = tmdb_service.get_details(search_res[0]['id'])

    if api_movie:
        # Get TMDB API similar movies
        api_similar = tmdb_service.get_similar(api_movie['id'], limit=10)
        
        # Add transparent explanation badge
        for m in api_similar:
            m['similarity_label'] = "API Suggested"
            m['explanation'] = "Suggested via TMDB's related title algorithms based on shared keywords and genres."

        return render_template(
            'results.html',
            is_ml=False,
            is_api_fallback=True,
            query_movie=api_movie,
            cluster_used=None,
            total_cluster_movies=0,
            recommendations=api_similar,
            watchlist_ids=user_watchlist_ids
        )

    flash(f"Could not find recommendations for '{query}'. Please try selecting a movie from the catalog.", 'warning')
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
    
    # First search TMDB for high quality poster thumbnails
    tmdb_results = tmdb_service.search(query, page=1)
    if tmdb_results:
        return jsonify(tmdb_results[:8])

    # Fallback to local recommender search
    recommender = MovieRecommender.get_instance()
    results = recommender.search_movies(query, limit=8)
    for r in results:
        tmdb_service.enrich_movie(r)
    return jsonify(results)

@rec_bp.route('/api/movie/<int:movie_id>')
def api_movie_details(movie_id):
    # Try TMDB service first for full backdrop, cast and details
    details = tmdb_service.get_details(movie_id)
    if details:
        return jsonify({'success': True, 'movie': details})
    
    recommender = MovieRecommender.get_instance()
    movie = recommender.get_movie_by_id(movie_id)
    if not movie:
        return jsonify({'success': False, 'error': 'Movie not found'}), 404
    enriched = tmdb_service.enrich_movie(movie)
    return jsonify({'success': True, 'movie': enriched})

@rec_bp.route('/api/movies/<movie_id>/similar', methods=['GET', 'POST'])
@rec_bp.route('/api/movies/similar', methods=['GET', 'POST'])
def api_movie_similar(movie_id=None):
    """
    Dedicated JSON API endpoint for similar movie recommendations.
    Accepts movie ID in URL path and optional movie title via JSON body, query param, or form.
    Executes ML recommendation engine if available in trained dataset,
    otherwise cleanly falls back to TMDB similar endpoint.
    """
    # Extract movie_id from param, args, or json body
    if not movie_id:
        movie_id = request.args.get('movie_id')
        if not movie_id and request.is_json:
            data = request.get_json(silent=True) or {}
            movie_id = data.get('movie_id') or data.get('id')

    if not movie_id or str(movie_id).strip().lower() in ['none', 'null', 'undefined', '']:
        # If title is provided, allow searching by title alone
        title = request.args.get('title') or (request.get_json(silent=True) or {}).get('title') if request.is_json else None
        if not title:
            return jsonify({'success': False, 'error': 'A valid movie ID or title must be provided.'}), 400
        movie_id_str = title.strip()
    else:
        movie_id_str = str(movie_id).strip()

    # Extract optional title from request
    title = None
    if request.is_json:
        data = request.get_json(silent=True) or {}
        title = data.get('title')
    if not title:
        title = request.args.get('title') or request.form.get('title')

    recommender = MovieRecommender.get_instance()
    user = get_current_user()
    watchlist_ids = set()
    if user:
        watchlist_ids = set([w.movie_id for w in db_session.query(Watchlist.movie_id).filter_by(user_id=user.id).all()])

    # 1. Attempt ML recommendation (TF-IDF + K-Means + Cosine Similarity)
    try:
        ml_result = recommender.recommend(movie_id_str, query_title=title, top_n=10)
        if ml_result.get('success'):
            selected_movie = tmdb_service.enrich_movie(ml_result['query_movie'])
            enriched_recs = []
            for rec in ml_result['recommendations']:
                enriched = tmdb_service.enrich_movie(rec)
                enriched['is_in_watchlist'] = (enriched['id'] in watchlist_ids)
                enriched['source'] = 'machine_learning'
                enriched_recs.append(enriched)

            # Record in user history if authenticated
            if user:
                try:
                    history_entry = RecommendationHistory(
                        user_id=user.id,
                        selected_movie_id=selected_movie['id'],
                        selected_movie_title=selected_movie['title'],
                        cluster_id=ml_result['cluster_used']
                    )
                    history_entry.set_recommendations(enriched_recs)
                    db_session.add(history_entry)
                    db_session.commit()
                except Exception as e:
                    db_session.rollback()

            return jsonify({
                'success': True,
                'source': 'machine_learning',
                'source_label': 'Machine Learning (TF-IDF & K-Means)',
                'selected_movie': selected_movie,
                'cluster_used': ml_result['cluster_used'],
                'total_cluster_movies': ml_result['total_cluster_movies'],
                'recommendations': enriched_recs,
                'count': len(enriched_recs)
            }), 200

    except Exception as e:
        print(f"[-] ML recommendation error for {movie_id_str}: {e}")

    # 2. Movie not in trained dataset -> TMDB API Fallback
    try:
        api_movie = None
        if movie_id_str.isdigit():
            api_movie = tmdb_service.get_details(int(movie_id_str))
        
        if not api_movie and title:
            search_res = tmdb_service.search(title)
            if search_res:
                api_movie = tmdb_service.get_details(search_res[0]['id'])

        if api_movie:
            api_similar = tmdb_service.get_similar(api_movie['id'], limit=10)
            if api_similar:
                for m in api_similar:
                    m['similarity_label'] = 'TMDB Similar Movies'
                    m['similarity_score'] = None
                    m['similarity_percent'] = None
                    m['source'] = 'tmdb_api'
                    m['is_in_watchlist'] = (m['id'] in watchlist_ids)
                    m['explanation'] = "Curated via TMDB's related title algorithms based on thematic and genre similarity."

                return jsonify({
                    'success': True,
                    'source': 'tmdb_api',
                    'source_label': 'TMDB Similar Movies',
                    'selected_movie': api_movie,
                    'cluster_used': None,
                    'total_cluster_movies': 0,
                    'recommendations': api_similar,
                    'count': len(api_similar)
                }), 200
    except Exception as e:
        print(f"[-] TMDB similar fallback error for {movie_id_str}: {e}")

    # 3. Neither ML nor TMDB found results
    return jsonify({
        'success': False,
        'error': f"Movie '{title or movie_id_str}' was not found in the trained dataset, and live suggestions could not be loaded.",
        'selected_movie': None,
        'recommendations': [],
        'count': 0
    }), 404
