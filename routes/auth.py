import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.models import db_session, User
from routes.auth_helper import login_user, logout_user

auth_bp = Blueprint('auth', __name__)

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        # Validation
        if not email or not password:
            flash('Both email and password are required.', 'danger')
            return render_template('login.html', email=email)

        user = db_session.query(User).filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Invalid email or password. Please try again.', 'danger')
            return render_template('login.html', email=email)

        # Login success
        login_user(user, remember=remember)
        flash(f'Welcome back, {user.full_name}!', 'success')
        
        next_page = request.args.get('next')
        if next_page and not next_page.startswith('//') and not next_page.startswith('http'):
            return redirect(next_page)
        return redirect(url_for('main.dashboard'))

    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('user_id'):
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Server-side validations
        if not full_name or not email or not password or not confirm_password:
            flash('All fields are required.', 'danger')
            return render_template('register.html', full_name=full_name, email=email)

        if len(full_name) < 2:
            flash('Full name must be at least 2 characters long.', 'danger')
            return render_template('register.html', full_name=full_name, email=email)

        if not re.match(EMAIL_REGEX, email):
            flash('Please enter a valid email address.', 'danger')
            return render_template('register.html', full_name=full_name, email=email)

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('register.html', full_name=full_name, email=email)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', full_name=full_name, email=email)

        # Check existing user
        existing_user = db_session.query(User).filter_by(email=email).first()
        if existing_user:
            flash('An account with this email already exists. Please sign in.', 'warning')
            return render_template('register.html', full_name=full_name, email=email)

        # Create new user
        new_user = User(full_name=full_name, email=email)
        new_user.set_password(password)
        db_session.add(new_user)
        try:
            db_session.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db_session.rollback()
            flash('An error occurred during registration. Please try again.', 'danger')
            return render_template('register.html', full_name=full_name, email=email)

    return render_template('register.html')

@auth_bp.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/forgot-password')
def forgot_password():
    flash('For demo/academic security purposes, password reset is managed via your Profile settings when logged in, or ask the system administrator.', 'info')
    return redirect(url_for('auth.login'))

