import os
import sys
from flask import Flask, render_template

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

    # Register Blueprints
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.recommendations import rec_bp
    from routes.watchlist import watchlist_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(rec_bp)
    app.register_blueprint(watchlist_bp)

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

    # Custom Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('404.html', error_title="500 - Server Error", error_msg="An internal server error occurred. Our system is working to resolve it."), 500

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"[*] Starting CineMatch AI Server on http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port, debug=True)

