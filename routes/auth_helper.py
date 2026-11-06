from functools import wraps
from flask import session, redirect, url_for, flash, request, jsonify
from database.models import db_session, User

def login_user(user, remember=False):
    """Sets user identity in the Flask session."""
    session.clear()
    session['user_id'] = user.id
    session['user_name'] = user.full_name
    session['user_email'] = user.email
    if remember:
        session.permanent = True

def logout_user():
    """Clears user session."""
    session.clear()

def get_current_user():
    """Fetches the current logged in user from database."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    return db_session.get(User, user_id)

def login_required(f):
    """Decorator to protect routes requiring authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Authentication required. Please log in.'}), 401
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        user = db_session.get(User, user_id)
        if not user:
            session.clear()
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Session expired. Please log in.'}), 401
            flash('Session expired. Please log in again.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
            
        return f(*args, **kwargs)
    return decorated_function

