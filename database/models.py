import os
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config

Base = declarative_base()

def utc_now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    watchlist_items = relationship('Watchlist', back_populates='user', cascade='all, delete-orphan')
    recommendation_histories = relationship('RecommendationHistory', back_populates='user', cascade='all, delete-orphan')

    def set_password(self, password):
        """Hashes the user password using Werkzeug."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifies the password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'email': self.email,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

class Watchlist(Base):
    __tablename__ = 'watchlist'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    movie_id = Column(Integer, nullable=False)
    movie_title = Column(String(255), nullable=False)
    release_year = Column(Integer, nullable=True)
    vote_average = Column(String(20), nullable=True)
    genres = Column(String(255), nullable=True)
    poster_path = Column(String(255), nullable=True)
    backdrop_path = Column(String(255), nullable=True)
    added_at = Column(DateTime, default=utc_now)

    # Relationship
    user = relationship('User', back_populates='watchlist_items')

    # Prevent duplicate entries for the same user and movie
    __table_args__ = (
        UniqueConstraint('user_id', 'movie_id', name='uq_user_movie_watchlist'),
    )

    def to_dict(self):
        poster_url = f"{Config.TMDB_IMAGE_BASE_URL}{self.poster_path}" if self.poster_path else None
        return {
            'id': self.id,
            'user_id': self.user_id,
            'movie_id': self.movie_id,
            'movie_title': self.movie_title,
            'release_year': self.release_year,
            'vote_average': self.vote_average,
            'genres': self.genres,
            'poster_path': self.poster_path,
            'poster_url': poster_url,
            'added_at': self.added_at.strftime('%Y-%m-%d %H:%M:%S') if self.added_at else None
        }

class RecommendationHistory(Base):
    __tablename__ = 'recommendation_history'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    selected_movie_id = Column(Integer, nullable=False)
    selected_movie_title = Column(String(255), nullable=False)
    recommended_movies_json = Column(Text, nullable=False)  # JSON serialized recommendations
    cluster_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationship
    user = relationship('User', back_populates='recommendation_histories')

    def get_recommendations(self):
        try:
            return json.loads(self.recommended_movies_json)
        except Exception:
            return []

    def set_recommendations(self, recs_list):
        self.recommended_movies_json = json.dumps(recs_list)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'selected_movie_id': self.selected_movie_id,
            'selected_movie_title': self.selected_movie_title,
            'cluster_id': self.cluster_id,
            'recommendations': self.get_recommendations(),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

class GenreOverride(Base):
    __tablename__ = 'genre_overrides'

    id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, unique=True, nullable=False, index=True)
    movie_title = Column(String(255), nullable=False)
    genres_json = Column(Text, nullable=False)  # JSON list of genre names
    genres_str = Column(String(255), nullable=False)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def get_genres(self):
        try:
            return json.loads(self.genres_json)
        except Exception:
            return [g.strip() for g in self.genres_str.split(',') if g.strip()]

    def set_genres(self, genres_list):
        if isinstance(genres_list, str):
            genres_list = [g.strip() for g in genres_list.split(',') if g.strip()]
        self.genres_json = json.dumps(genres_list)
        self.genres_str = ", ".join(genres_list)

    def to_dict(self):
        return {
            'movie_id': self.movie_id,
            'movie_title': self.movie_title,
            'genres': self.get_genres(),
            'genres_str': self.genres_str,
            'notes': self.notes,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }

# Database engine and session factory
try:
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
except Exception:
    pass
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, connect_args={"check_same_thread": False})
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine))

def init_db():
    """Creates database tables if they do not exist."""
    try:
        Base.metadata.create_all(bind=engine)
        print(f"[SUCCESS] Database tables verified at {Config.DATABASE_PATH}")
    except Exception as e:
        print(f"[!] init_db warning (read-only environment): {e}")
