import os
import sys
from flask import Flask, render_template, request, jsonify

from config import Config
from database.models import init_db, db_session
from ml.recommendation import MovieRecommender

def create_app():
    """Application factory for the Movie Recommendation System."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize Database
    with app.app_context():
        init_db()

    # Preload recommendation engine models into memory
    print("[*] Pre-warming Recommendation ML Models...")
    MovieRecommender.get_instance()

    # Register Blueprints (with dual-path support for both package structure and root placement)
    try:
        from routes.auth import auth_bp
        from routes.main import main_bp
        from routes.recommendations import rec_bp
        from routes.watchlist import watchlist_bp
    except (ImportError, ModuleNotFoundError):
        from auth import auth_bp
        from main import main_bp
        from recommendations import rec_bp
        from watchlist import watchlist_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(rec_bp)
    app.register_blueprint(watchlist_bp)

    # Global CORS and security headers for API endpoints
    @app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,X-Requested-With'
        response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
        return response

    # Database session teardown
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()

    # Context processors for global template variables
    @app.context_processor
    def inject_globals():
        return {
            'app_title': 'CineMatch AI',
            'app_tagline': 'Intelligent Movie Recommendation Platform'
        }

    # Custom Error Handlers (Always return JSON for API requests)
    @app.errorhandler(404)
    def page_not_found(e):
        if request.path.startswith('/api/') or request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'API endpoint not found', 'status': 404}), 404
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        if request.path.startswith('/api/') or request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Internal server error while processing request', 'status': 500}), 500
        return render_template('404.html', error_title="500 - Server Error", error_msg="An internal server error occurred. Our system is working to resolve it."), 500

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"[*] Starting CineMatch AI Server on http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port, debug=True)

