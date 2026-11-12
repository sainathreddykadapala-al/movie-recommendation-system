from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from database.models import db_session, Watchlist
from routes.auth_helper import login_required, get_current_user
from ml.recommendation import MovieRecommender

watchlist_bp = Blueprint('watchlist', __name__)

@watchlist_bp.route('/watchlist')
@login_required
def index():
    user = get_current_user()
    items = db_session.query(Watchlist).filter_by(
        user_id=user.id
    ).order_by(Watchlist.added_at.desc()).all()

    return render_template('watchlist.html', watchlist_items=items)

@watchlist_bp.route('/watchlist/add', methods=['POST'])
@login_required
def add():
    user = get_current_user()
    
    # Accept both Form data and JSON
    if request.is_json:
        data = request.get_json()
        movie_id = data.get('movie_id')
    else:
        movie_id = request.form.get('movie_id')

    if not movie_id:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Missing movie_id'}), 400
        flash('Movie ID is required.', 'danger')
        return redirect(request.referrer or url_for('main.dashboard'))

    try:
        movie_id = int(movie_id)
    except ValueError:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Invalid movie ID'}), 400
        flash('Invalid movie ID.', 'danger')
        return redirect(request.referrer or url_for('main.dashboard'))

    # Check for duplicate
    existing = db_session.query(Watchlist).filter_by(user_id=user.id, movie_id=movie_id).first()
    if existing:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Movie is already in your watchlist.'}), 200
        flash('Movie is already in your watchlist.', 'info')
        return redirect(request.referrer or url_for('watchlist.index'))

    # Get movie details from recommender or TMDB API
    from services.tmdb_service import tmdb_service
    recommender = MovieRecommender.get_instance()
    movie = recommender.get_movie_by_id(movie_id)

    movie_title = None
    release_year = None
    vote_average = None
    genres = None
    poster_path = None
    backdrop_path = None

    if movie:
        movie_title = movie.get('title')
        release_year = int(movie['release_year']) if movie.get('release_year') else 2000
        vote_average = str(round(float(movie.get('vote_average', 0.0)), 1))
        genres = movie.get('genres_str', 'General')
        # Check if poster is in request data or TMDB details
        if request.is_json and request.get_json().get('poster_path'):
            poster_path = request.get_json().get('poster_path')
        else:
            enriched = tmdb_service.enrich_movie(movie)
            poster_path = enriched.get('poster_path')
            backdrop_path = enriched.get('backdrop_path')
    else:
        # Fetch from TMDB API
        tmdb_data = tmdb_service.get_details(movie_id)
        if tmdb_data:
            movie_title = tmdb_data.get('title')
            release_year = int(tmdb_data['release_year']) if tmdb_data.get('release_year') and tmdb_data['release_year'] != 'N/A' else 2024
            vote_average = str(tmdb_data.get('vote_average', 0.0))
            genres = tmdb_data.get('genres_str', 'General')
            poster_path = tmdb_data.get('poster_path')
            backdrop_path = tmdb_data.get('backdrop_path')
        elif request.is_json:
            # Fallback to payload passed from client
            d = request.get_json()
            movie_title = d.get('title', f"Movie #{movie_id}")
            release_year = d.get('release_year', 2024)
            vote_average = str(d.get('vote_average', '7.0'))
            genres = d.get('genres', 'General')
            poster_path = d.get('poster_path')

    if not movie_title:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Movie not found in dataset or TMDB'}), 404
        flash('Movie details could not be found.', 'danger')
        return redirect(request.referrer or url_for('watchlist.index'))

    # Create watchlist item
    item = Watchlist(
        user_id=user.id,
        movie_id=movie_id,
        movie_title=movie_title,
        release_year=release_year,
        vote_average=vote_average,
        genres=genres,
        poster_path=poster_path,
        backdrop_path=backdrop_path
    )
    db_session.add(item)
    try:
        db_session.commit()
        if request.is_json:
            return jsonify({'success': True, 'message': f"'{movie_title}' added to your watchlist!"}), 200
        flash(f"'{movie_title}' added to your watchlist!", 'success')
    except Exception as e:
        db_session.rollback()
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 500
        flash('Could not add to watchlist.', 'danger')

    return redirect(request.referrer or url_for('watchlist.index'))

@watchlist_bp.route('/watchlist/remove/<int:movie_id>', methods=['POST', 'DELETE'])
@login_required
def remove(movie_id):
    user = get_current_user()
    item = db_session.query(Watchlist).filter_by(user_id=user.id, movie_id=movie_id).first()

    if not item:
        if request.is_json or request.method == 'DELETE':
            return jsonify({'success': False, 'error': 'Movie not found in your watchlist.'}), 404
        flash('Movie not found in your watchlist.', 'warning')
        return redirect(request.referrer or url_for('watchlist.index'))

    title = item.movie_title
    db_session.delete(item)
    try:
        db_session.commit()
        if request.is_json or request.method == 'DELETE':
            return jsonify({'success': True, 'message': f"'{title}' removed from your watchlist."}), 200
        flash(f"'{title}' removed from your watchlist.", 'info')
    except Exception as e:
        db_session.rollback()
        if request.is_json or request.method == 'DELETE':
            return jsonify({'success': False, 'error': str(e)}), 500
        flash('Could not remove movie from watchlist.', 'danger')

    return redirect(request.referrer or url_for('watchlist.index'))

