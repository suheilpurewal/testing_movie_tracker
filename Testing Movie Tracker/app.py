from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime, timezone
import requests


app = Flask(__name__, template_folder="templates")


app.secret_key = 'super_secret_key_1234'
tmdb_api_key = '0be927d50945d1293a82faa8e65bbdf8'

# Configure the SQLite database
##use below when local
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
##Use below for HA Addon
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////data/test_users.db'
db = SQLAlchemy(app)

# Define a User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    ratings = db.relationship('Rating', cascade="all, delete", passive_deletes=True)
    attendance = db.relationship('MovieAttendance', back_populates="user", cascade="all, delete", passive_deletes=True)
    attended_movies = db.relationship('Movie', secondary='movie_attendance', overlaps="attendance,attended_movies")
    episode_ratings = db.relationship('EpisodeRating', backref='user', lazy=True, cascade="all, delete")
    episode_attendance = db.relationship('EpisodeAttendance', back_populates='user', lazy=True, cascade="all, delete")

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    watch_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    poster_path = db.Column(db.String(200))
    release_date = db.Column(db.String(20))
    overview = db.Column(db.Text)
    runtime = db.Column(db.Integer)  # Add this line to store the movie runtime in minutes

    attendance = db.relationship('MovieAttendance', back_populates='movie', lazy=True, cascade="all, delete-orphan", overlaps="attended_movies,attendees")
    ratings = db.relationship('Rating', backref='movie_ref', lazy=True, cascade="all, delete-orphan")
    attendees = db.relationship('User', secondary='movie_attendance', overlaps="attendance,attended_movies")
    
class MovieAttendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

    movie = db.relationship('Movie', back_populates='attendance', overlaps="attended_movies,attendees")
    user = db.relationship('User', back_populates='attendance', overlaps="attended_movies,attendees")

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id', ondelete='CASCADE'), nullable=False)
    rating = db.Column(db.Float, nullable=False)

class MovieRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    movie_title = db.Column(db.String(100), nullable=False)
    requested_by = db.Column(db.String(80), nullable=False)
    request_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    votes = db.Column(db.Integer, default=0)
    movie_id = db.Column(db.Integer)  # Add this line to store TMDb movie ID

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(80), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey('movie_request.id'), nullable=False)
    vote_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    request = db.relationship('MovieRequest', backref=db.backref('votes_list', lazy=True))

class TVShow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, unique=True)
    poster_path = db.Column(db.String(200))
    average_rating = db.Column(db.Float)
    tmdb_id = db.Column(db.Integer, nullable=False, unique=True)  # Add this line
    total_seasons = db.Column(db.Integer)  # Store total seasons
    # Relationship with episodes
    episodes = db.relationship('Episode', backref='tv_show', lazy=True, cascade="all, delete-orphan")

class Episode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    season_number = db.Column(db.Integer, nullable=False)
    episode_number = db.Column(db.Integer, nullable=False)
    runtime = db.Column(db.Integer)  # Duration in minutes
    air_date = db.Column(db.DateTime)
    watch_date = db.Column(db.DateTime, nullable=True)
    # Foreign key to associate with TV show
    tv_show_id = db.Column(db.Integer, db.ForeignKey('tv_show.id'), nullable=False)
    
    # Relationships for ratings and attendance
    ratings = db.relationship('EpisodeRating', backref='episode', lazy=True, cascade="all, delete-orphan")
    attendance = db.relationship('EpisodeAttendance', back_populates='episode', lazy='dynamic', cascade="all, delete-orphan")


class EpisodeRating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Float, nullable=False)
    
    # Foreign keys for user and episode association
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    episode_id = db.Column(db.Integer, db.ForeignKey('episode.id'), nullable=False)

class EpisodeAttendance(db.Model):
    __tablename__ = 'episode_attendance'
    id = db.Column(db.Integer, primary_key=True)
    episode_id = db.Column(db.Integer, db.ForeignKey('episode.id'), nullable=False)  # Fix 'episodes' to 'episode'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)       # Fix 'users' to 'user'
    
    # Relationships to access user and episode details
    episode = db.relationship('Episode', back_populates='attendance')
    user = db.relationship('User', back_populates='episode_attendance')  
    
# Create the database tables within an application context
with app.app_context():
    db.create_all()

    # Add "Suhail" as a default user if not exists
    suhail_user = User.query.filter_by(name="Suhail").first()
    if not suhail_user:
        suhail_user = User(name="Suhail")
        db.session.add(suhail_user)
        db.session.commit()

##################### ROUTES ##########################################
@app.route('/')
def home():
    users = User.query.all()
    return render_template('select_user.html', users=users, user=None)

@app.route('/index')
def index():
    return redirect(url_for('home'))

@app.route('/select_user', methods=['GET', 'POST'])
def select_user():
    if request.method == 'POST':
        selected_user = request.form['user_name']
        session['user_name'] = selected_user  # Store username in session
        return redirect(url_for('dashboard', user_name=selected_user))
    users = User.query.all()
    return render_template('select_user.html', users=users)

############# DEBUG PAGE #########################
@app.route('/debug/movies')
def debug_movies():
    movies = Movie.query.all()
    debug_info = []

    for movie in movies:
        debug_info.append({
            "title": movie.title,
            "runtime": movie.runtime,
            "watch_date": movie.watch_date,
            "attendees": [attendee.name for attendee in movie.attendees]
        })

    print("DEBUG INFO:", debug_info)  # Print to console
    return jsonify(debug_info)  # Return data in JSON format to view in the browser

############# DASHBOARD PAGE #########################
@app.route('/dashboard')
def dashboard():
    user_name = request.args.get('user_name')
    user = User.query.filter_by(name=user_name).first_or_404()

    # Calculate total watch time for the user in hours
    total_watch_time = sum((movie.runtime or 0) for movie in user.attended_movies) / 60

    # Total movies watched by all users
    total_movies_watched = Movie.query.count()

    # Calculate average rating given by the user
    user_ratings = [rating.rating for rating in user.ratings]
    average_user_rating = sum(user_ratings) / len(user_ratings) if user_ratings else None

    # Highest and lowest rated movies based on all ratings
    highest_rated_movie = (
        Movie.query
        .join(Rating)
        .group_by(Movie.id)
        .order_by(db.func.avg(Rating.rating).desc())
        .first()
    )
    lowest_rated_movie = (
        Movie.query
        .join(Rating)
        .group_by(Movie.id)
        .order_by(db.func.avg(Rating.rating).asc())
        .first()
    )

    # Retrieve the average rating for these movies if they exist
    highest_rating = (
        db.session.query(db.func.avg(Rating.rating))
        .filter(Rating.movie_id == highest_rated_movie.id)
        .scalar() if highest_rated_movie else None
    )
    lowest_rating = (
        db.session.query(db.func.avg(Rating.rating))
        .filter(Rating.movie_id == lowest_rated_movie.id)
        .scalar() if lowest_rated_movie else None
    )

    # Find user with the highest and lowest average rating
    highest_avg_rating_user = (
        db.session.query(User, db.func.avg(Rating.rating).label('avg_rating'))
        .join(Rating)
        .group_by(User.id)
        .order_by(db.func.avg(Rating.rating).desc())
        .first()
    )
    lowest_avg_rating_user = (
        db.session.query(User, db.func.avg(Rating.rating).label('avg_rating'))
        .join(Rating)
        .group_by(User.id)
        .order_by(db.func.avg(Rating.rating).asc())
        .first()
    )

    # Retrieve avg ratings if the users exist
    highest_avg_rating = highest_avg_rating_user[1] if highest_avg_rating_user else None
    highest_avg_rating_user = highest_avg_rating_user[0] if highest_avg_rating_user else None

    lowest_avg_rating = lowest_avg_rating_user[1] if lowest_avg_rating_user else None
    lowest_avg_rating_user = lowest_avg_rating_user[0] if lowest_avg_rating_user else None

    # Retrieve unrated movies attended by the user
    attended_movie_titles = [attendance.movie.title for attendance in MovieAttendance.query.filter_by(user_id=user.id).all()]
    rated_movie_titles = [rating.movie_ref.title for rating in user.ratings]
    unrated_movies = db.session.query(Movie).filter(
        Movie.title.in_(attended_movie_titles),
        ~Movie.title.in_(rated_movie_titles)
    ).all()

    # Logic for episodes to rate
    unrated_episodes = db.session.query(Episode).join(EpisodeAttendance).filter(
        EpisodeAttendance.user_id == user.id,
        ~Episode.id.in_([rating.episode_id for rating in user.episode_ratings])
    ).all()

    # Additional TV show stats
    total_tv_shows_watched = db.session.query(db.func.count(TVShow.id)).join(Episode).filter(Episode.watch_date.isnot(None)).scalar()

    highest_rated_episode = (
        db.session.query(Episode)
        .join(EpisodeRating)
        .group_by(Episode.id)
        .order_by(db.func.avg(EpisodeRating.rating).desc())
        .first()
    )
    lowest_rated_episode = (
        db.session.query(Episode)
        .join(EpisodeRating)
        .group_by(Episode.id)
        .order_by(db.func.avg(EpisodeRating.rating).asc())
        .first()
    )

    highest_episode_rating = (
        db.session.query(db.func.max(EpisodeRating.rating))
        .filter(EpisodeRating.episode_id == highest_rated_episode.id)
        .scalar() if highest_rated_episode else None
    )
    lowest_episode_rating = (
        db.session.query(db.func.min(EpisodeRating.rating))
        .filter(EpisodeRating.episode_id == lowest_rated_episode.id)
        .scalar() if lowest_rated_episode else None
    )

    # Calculate the average TV show rating for the user
    average_tv_show_rating = db.session.query(db.func.avg(EpisodeRating.rating)).filter(EpisodeRating.user_id == user.id).scalar()

    # TV show with the most episodes watched
    tv_show_most_episodes_watched = (
        db.session.query(TVShow, db.func.count(Episode.id).label('episode_count'))
        .join(Episode)
        .filter(Episode.watch_date.isnot(None))
        .group_by(TVShow.id)
        .order_by(db.func.count(Episode.id).desc())
        .first()
    )

    return render_template(
        'dashboard.html',
        user=user,
        total_watch_time=total_watch_time,
        total_movies_watched=total_movies_watched,
        average_user_rating=average_user_rating,
        highest_rated_movie=highest_rated_movie,
        lowest_rated_movie=lowest_rated_movie,
        highest_rating=highest_rating,
        lowest_rating=lowest_rating,
        highest_avg_rating_user=highest_avg_rating_user,
        lowest_avg_rating_user=lowest_avg_rating_user,
        highest_avg_rating=highest_avg_rating,
        lowest_avg_rating=lowest_avg_rating,
        unrated_movies=unrated_movies,
        unrated_episodes=unrated_episodes,
        total_tv_shows_watched=total_tv_shows_watched,
        highest_rated_episode=highest_rated_episode,
        highest_episode_rating=highest_episode_rating,
        lowest_rated_episode=lowest_rated_episode,
        lowest_episode_rating=lowest_episode_rating,
        average_tv_show_rating=average_tv_show_rating,
        tv_show_most_episodes_watched=tv_show_most_episodes_watched
    )
###################### ADMIN PAGE ROUTES #########################

@app.route('/admin')
def admin_page():
    user_name = session.get('user_name', 'DefaultUser')
    user = User.query.filter_by(name=user_name).first()
    users = User.query.all()
    movies = Movie.query.all()
    is_admin = user_name == "Suhail"

    return render_template('admin.html', user_name=user_name, user=user, users=users, movies=movies, is_admin=is_admin)

@app.route('/admin/manage_requests', methods=['GET', 'POST'])
def manage_requests():
    user_name = session.get('user_name', 'Guest')  # Use session data
    movie_requests = MovieRequest.query.all()
    return render_template('admin_requests.html', movie_requests=movie_requests, user_name=user_name)

@app.route('/admin/manage_ratings')
def manage_all_ratings():
    # Get all movies with user ratings
    movies_with_ratings = Movie.query.all()
    
    # Prepare a dictionary with movies and associated ratings per user
    movie_ratings_data = []
    for movie in movies_with_ratings:
        movie_info = {
            'id': movie.id,
            'title': movie.title,
            'ratings': [{'user': rating.user.name, 'score': rating.rating, 'user_id': rating.user_id} for rating in movie.ratings]
        }
        movie_ratings_data.append(movie_info)
    
    return render_template('manage_ratings.html', movies=movie_ratings_data)

@app.route('/admin/manage_ratings/<int:movie_id>')
def manage_ratings_for_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    ratings = Rating.query.filter_by(movie_id=movie_id).all()
    
    # Get all ratings for the movie
    movie_ratings = [
        {'user': rating.user.name, 'score': rating.rating, 'user_id': rating.user_id} 
        for rating in ratings
    ]
    
    return render_template('manage_movie_ratings.html', movie=movie, movie_ratings=movie_ratings)

@app.route('/update_rating', methods=['POST'])
def update_rating():
    user_id = request.form.get('user_id')
    movie_id = request.form.get('movie_id')
    new_rating = request.form.get('new_rating')

    # Find the rating record and update it
    rating = Rating.query.filter_by(user_id=user_id, movie_id=movie_id).first()
    if rating:
        rating.rating = float(new_rating)
        db.session.commit()
        flash("Rating updated successfully!", "success")
    else:
        flash("Rating record not found.", "danger")
    
    return redirect(url_for('manage_ratings', movie_id=movie_id))

# Route to mark a request as watched
@app.route('/admin/mark_watched/<int:request_id>', methods=['POST'])
def mark_request_as_watched(request_id):
    movie_request = MovieRequest.query.get_or_404(request_id)
    movie_request.status = 'watched'
    # Set watched date if needed or update accordingly
    db.session.commit()
    user_name = session.get('user_name', 'DefaultUser') 
    return redirect(url_for('manage_requests', user_name=user_name))

# Route to delete a request
@app.route('/admin/delete_request/<int:request_id>', methods=['POST'])
def delete_request(request_id):
    movie_request = MovieRequest.query.get_or_404(request_id)
    db.session.delete(movie_request)
    db.session.commit()
    user_name = session.get('user_name', 'DefaultUser') 
    return redirect(url_for('manage_requests', user_name=user_name))

# Route to edit a request
@app.route('/admin/edit_request/<int:request_id>', methods=['POST'])
def edit_request(request_id):
    movie_request = MovieRequest.query.get_or_404(request_id)
    new_title = request.form['new_title']
    movie_request.movie_title = new_title
    db.session.commit()
    user_name = session.get('user_name', 'DefaultUser') 
    return redirect(url_for('manage_requests', user_name=user_name))

@app.route('/admin/requests')
def admin_requests():
    movie_requests = MovieRequest.query.all()  # or any logic to retrieve requests
    return render_template('admin_requests.html', movie_requests=movie_requests)

# Edit Movie Route
@app.route('/edit_movie/<int:movie_id>', methods=['GET', 'POST'])
def edit_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    if request.method == 'POST':
        movie.title = request.form['title']
        db.session.commit()
        return redirect(url_for('admin_page', user_name=request.form['user_name']))
    return render_template('edit_movie.html', movie=movie)

# Delete Movie Route
@app.route('/delete_movie/<int:movie_id>', methods=['POST'])
def delete_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    db.session.delete(movie)
    db.session.commit()
    return redirect(url_for('admin_page', user_name=request.form['user_name']))

@app.route('/admin/edit_attendance/<int:movie_id>', methods=['GET', 'POST'])
def admin_edit_attendance(movie_id):
    user_name = session.get('user_name', 'Guest')  # Use session data instead
    movie = Movie.query.get_or_404(movie_id)
    users = User.query.all()
    attended_users = [attendance.user_id for attendance in movie.attendance]

    if request.method == 'POST':
        selected_user_ids = request.form.getlist('users')
        MovieAttendance.query.filter_by(movie_id=movie_id).delete()
        for user_id in selected_user_ids:
            new_attendance = MovieAttendance(movie_id=movie_id, user_id=user_id)
            db.session.add(new_attendance)
        db.session.commit()

        return redirect(url_for('admin_page'))  # No need to pass user_name here

    return render_template(
        'edit_attendance.html',
        movie=movie,
        users=users,
        attended_users=attended_users,
        user_name=user_name
    )


# Edit User Route
@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.name = request.form['name']
        db.session.commit()
        return redirect(url_for('admin_page', user_name=request.form['user_name']))
    return render_template('edit_user.html', user=user)

# Delete User Route
@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin_page', user_name=request.form['user_name']))


###############################################################

# Route to vote for a movie request
@app.route('/vote_movie/<int:request_id>', methods=['POST'])
def vote_movie(request_id):
    user_name = request.form['user_name']
    
    # Check if the user has already voted for this request
    existing_vote = Vote.query.filter_by(user_name=user_name, request_id=request_id).first()
    if existing_vote:
        message = "You have already voted for this request."
        return redirect(url_for('movies_page', user_name=user_name, message=message))

    # Increment vote count for the request
    movie_request = MovieRequest.query.get(request_id)
    if movie_request:
        movie_request.votes += 1
        new_vote = Vote(user_name=user_name, request_id=request_id)
        db.session.add(new_vote)
        db.session.commit()

    return redirect(url_for('movies_page', user_name=user_name))


@app.route('/request_movie', methods=['GET', 'POST'])
def request_movie():
    if request.method == 'POST':
        movie_title = request.form.get('movie_title')
        requested_by = request.form.get('requested_by')
        movie_id = request.form.get('movie_id')  # Retrieve the movie_id from the form

        # Check if the movie request already exists
        existing_request = MovieRequest.query.filter_by(movie_title=movie_title).first()
        if existing_request:
            message = "This movie has already been requested."
            return render_template('request_movie.html', message=message, users=User.query.all())
        
        # Create a new movie request with movie_id
        new_request = MovieRequest(movie_title=movie_title, requested_by=requested_by, votes=0, movie_id=movie_id)
        db.session.add(new_request)
        db.session.commit()

        return redirect(url_for('movies_page', user_name=requested_by))
    else:
        return render_template('request_movie.html', users=User.query.all())

@app.route('/add_user', methods=['POST'])
def add_user():
    new_user_name = request.form.get('new_user_name')
    if new_user_name:
        existing_user = User.query.filter_by(name=new_user_name).first()
        if not existing_user:
            new_user = User(name=new_user_name)
            db.session.add(new_user)
            db.session.commit()
    return redirect(url_for('admin_page', user_name=session.get('user_name')))

@app.route('/add_movie', methods=['POST'])
def add_movie():
    user_name = request.form['user_name']
    movie_title = request.form['movie']

    if user_name == "Suhail":
        new_movie = Movie(title=movie_title, watch_date=datetime.utcnow())
        db.session.add(new_movie)
        db.session.commit()

    return redirect(url_for('movies_page', user_name=user_name))


@app.route('/rate_movie', methods=['POST'])
def rate_movie():
    user_name = request.args.get('user_name')
    movie_name = request.args.get('movie_name')
    rating = round(float(request.form.get('rating')), 1)
    
    # Query the database for the user and movie
    user = User.query.filter_by(name=user_name).first()
    movie = Movie.query.filter_by(title=movie_name).first()

    if user and movie and (1.0 <= rating <= 10.0):
        # Check if the user has already rated this movie
        existing_rating = Rating.query.filter_by(user_id=user.id, movie_id=movie.id).first()
        if existing_rating:
            # Update the existing rating
            existing_rating.rating = rating
        else:
            # Add a new rating
            new_rating = Rating(user_id=user.id, movie_id=movie.id, rating=rating)
            db.session.add(new_rating)
        
        db.session.commit()

    # Redirect back to the dashboard with user_name included
    return redirect(url_for('movies_page', user_name=user_name))

@app.route('/movie_details/<int:movie_id>')

def movie_details(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    
    # Calculate the average rating for this movie
    average_rating = db.session.query(func.avg(Rating.rating)).filter(Rating.movie_id == movie.id).scalar()
    average_rating = round(average_rating, 1) if average_rating else 'N/A'

    # Get all attendees and their ratings
    ratings = db.session.query(Rating, User).join(User, Rating.user_id == User.id).filter(Rating.movie_id == movie.id).all()

    # Build modal content
    content = {
        "title": movie.title,
        "poster_path": movie.poster_path,
        "watch_date": movie.watch_date.strftime('%Y-%m-%d') if movie.watch_date else "N/A",
        "average_rating": average_rating,
        "attendees": [{"name": user.name, "rating": rating.rating} for rating, user in ratings]
    }

    return jsonify(content)

@app.route('/movie_request_details/<int:request_id>')
def movie_request_details(request_id):
    movie_request = MovieRequest.query.get_or_404(request_id)

    # Fetch additional movie details from TMDb using the stored movie ID
    tmdb_api_key = '0be927d50945d1293a82faa8e65bbdf8'
    movie_id = movie_request.movie_id  # Ensure movie_id is stored during movie request

    tmdb_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={tmdb_api_key}"
    response = requests.get(tmdb_url)
    if response.status_code == 200:
        tmdb_data = response.json()
        movie_details = {
            "title": movie_request.movie_title,
            "requested_by": movie_request.requested_by,
            "request_date": movie_request.request_date.strftime('%Y-%m-%d'),
            "runtime": tmdb_data.get("runtime", "N/A"),
            "overview": tmdb_data.get("overview", "No overview available."),
            "poster_path": tmdb_data.get("poster_path", "")
        }
    else:
        movie_details = {
            "title": movie_request.movie_title,
            "requested_by": movie_request.requested_by,
            "request_date": movie_request.request_date.strftime('%Y-%m-%d'),
            "runtime": "N/A",
            "overview": "No overview available.",
            "poster_path": ""
        }

    return jsonify(movie_details)

@app.route('/watched_movie_details/<int:movie_id>')
def watched_movie_details(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    average_rating = db.session.query(func.avg(Rating.rating)).filter(Rating.movie_id == movie.id).scalar()
    average_rating = round(average_rating, 1) if average_rating else 'N/A'

    movie_details = {
        "title": movie.title,
        "release_date": movie.watch_date.strftime('%Y-%m-%d'),
        "poster_path": movie.poster_path,         # Assuming you've saved this when added
        "overview": movie.overview,               # Assuming you've saved this when added
        "average_rating": average_rating
    }
    return jsonify(movie_details)

import requests

@app.route('/admin/add_watched_movie', methods=['GET', 'POST'])
def add_watched_movie():
    if request.method == 'POST':
        movie_title = request.form.get('movie_title')
        movie_id = request.form.get('movie_id')  # Assuming movie_id is passed in the form
        watch_date = request.form.get('watch_date')
        poster_path = request.form.get('movie_poster_path')
        release_date = request.form.get('movie_release_date')
        overview = request.form.get('movie_overview')

        # Convert watch_date to a datetime object if provided
        if watch_date:
            watch_date = datetime.strptime(watch_date, '%Y-%m-%d')

        # Fetch movie details from TMDb API to get the runtime
        api_key = "0be927d50945d1293a82faa8e65bbdf8"
        tmdb_api_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}"
        response = requests.get(tmdb_api_url)
        movie_data = response.json()

        # Get runtime from the API response (in minutes)
        runtime = movie_data.get('runtime', 0)  # Use 0 if runtime is not provided

        # Create a new movie entry in the Movie table
        new_movie = Movie(
            title=movie_title,
            watch_date=watch_date or datetime.utcnow(),
            poster_path=poster_path,
            release_date=release_date,
            overview=overview,
            runtime=runtime
        )
        db.session.add(new_movie)
        db.session.commit()

        return redirect(url_for('admin_page'))

    return render_template('admin.html')


####### MOVIES PAGE ###############
@app.route('/movies')
def movies_page():
    user_name = session.get('user_name')
    user = User.query.filter_by(name=user_name).first_or_404()
    is_admin = user_name == "Suhail"  # Adjust this check based on your desired admin users

    # Retrieve all movie requests
    movie_requests = MovieRequest.query.order_by(MovieRequest.votes.desc()).all()

    # Retrieve unrated movies attended by the user
    attended_movie_titles = [attendance.movie.title for attendance in MovieAttendance.query.filter_by(user_id=user.id).all()]
    rated_movie_titles = [rating.movie_ref.title for rating in user.ratings]
    unrated_movies = db.session.query(Movie).filter(
        Movie.title.in_(attended_movie_titles),
        ~Movie.title.in_(rated_movie_titles)
    ).all()

    # Retrieve all movies with average ratings and the user's rating (if available)
    all_movies = [
        {
            "id": movie.id,
            "title": movie.title,
            "watch_date": movie.watch_date,
            "average_rating": round(db.session.query(func.avg(Rating.rating)).filter(Rating.movie_id == movie.id).scalar() or 0, 1),
            "user_rating": db.session.query(Rating.rating).filter(Rating.movie_id == movie.id, Rating.user_id == user.id).scalar()  # Fetch the user's rating if it exists
        }
        for movie in db.session.query(Movie).all()
    ]

    # Retrieve only the movies the user has attended and rated
    personal_movies = [
        {
            "id": movie.id,
            "title": movie.title,
            "watch_date": movie.watch_date,
            "user_rating": rating.rating,
            "average_rating": round(db.session.query(func.avg(Rating.rating)).filter(Rating.movie_id == movie.id).scalar() or 0, 1)
        }
        for movie, rating in db.session.query(Movie, Rating).join(Rating).filter(Rating.user_id == user.id).all()
    ]

    return render_template(
        'movies.html',
        user=user,
        is_admin=is_admin,
        all_movies=all_movies,
        personal_movies=personal_movies,
        unrated_movies=unrated_movies,
        movie_requests=movie_requests
    )
############################################

########## TV SHOWS PAGE ##################
@app.route('/tv_shows')
def tv_shows():
    requested_shows = TVShow.query.all()
    return render_template('tv_shows.html', requested_shows=requested_shows)

@app.route('/autocomplete_tv_show')
def autocomplete_tv_show():
    query = request.args.get('query')
    url = f"https://api.themoviedb.org/3/search/tv?api_key={tmdb_api_key}&query={query}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        results = [{'title': show['name'], 'poster_path': show.get('poster_path'), 'tmdb_id': show['id']} for show in data['results']]
        return jsonify(results)
    return jsonify([]), 500

@app.route('/request_tv_show', methods=['POST'])
def request_tv_show():
    title = request.form.get('title')
    poster_path = request.form.get('poster_path')
    tmdb_id = request.form.get('tmdb_id')

    # Fetch show details from TMDb to get the total seasons
    url = f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={tmdb_api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        show_data = response.json()
        total_seasons = show_data.get('number_of_seasons', 1)  # Default to 1 if not available
    else:
        total_seasons = 1  # Fallback if API call fails

    # Check if the show already exists
    existing_show = TVShow.query.filter_by(tmdb_id=tmdb_id).first()
    if existing_show:
        flash("This TV show has already been requested!", "warning")
        return redirect(url_for('tv_shows'))

    # Add the new TV show to the database with total seasons
    new_tv_show = TVShow(title=title, poster_path=poster_path, tmdb_id=tmdb_id, total_seasons=total_seasons)
    db.session.add(new_tv_show)
    db.session.commit()

    flash("TV show requested successfully!", "success")
    return redirect(url_for('tv_shows'))

@app.route('/fetch_episodes/<int:show_id>')
def fetch_episodes(show_id):
    tv_show = TVShow.query.get_or_404(show_id)
    tmdb_show_id = tv_show.tmdb_id
    selected_seasons = request.args.getlist('seasons', type=int)

    if not selected_seasons:
        flash("No seasons selected for fetching.", "warning")
        return redirect(url_for('tv_show_details', show_id=show_id))

    # Fetch episodes for each selected season
    for season_number in selected_seasons:
        url = f"https://api.themoviedb.org/3/tv/{tmdb_show_id}/season/{season_number}?api_key={tmdb_api_key}"
        response = requests.get(url)
        print(f"Request URL: {url}")

        if response.status_code == 200:
            season_data = response.json()
            for episode_data in season_data['episodes']:
                # Convert air_date to a datetime object if it exists
                air_date_str = episode_data.get('air_date')
                air_date = datetime.strptime(air_date_str, '%Y-%m-%d') if air_date_str else None

                # Check if episode already exists to prevent duplicates
                existing_episode = Episode.query.filter_by(
                    tv_show_id=tv_show.id,
                    season_number=season_number,
                    episode_number=episode_data['episode_number']
                ).first()

                if not existing_episode:
                    # Add new episode
                    episode = Episode(
                        title=episode_data['name'],
                        season_number=season_number,
                        episode_number=episode_data['episode_number'],
                        runtime=episode_data.get('runtime', 0),
                        air_date=air_date,  # Use the converted datetime object
                        tv_show_id=tv_show.id
                    )
                    db.session.add(episode)
                    print(f"Added Episode {episode.episode_number} for Season {season_number}")
                else:
                    print(f"Episode {episode_data['episode_number']} for Season {season_number} already exists.")

    # Commit all episodes to the database after adding
    db.session.commit()
    flash("Episodes added successfully!", "success")
    return redirect(url_for('tv_show_details', show_id=show_id))

@app.route('/tv_show_details/<int:show_id>')
def tv_show_details(show_id):
    tv_show = TVShow.query.get_or_404(show_id)
    user_name = request.args.get('user_name')
    user = User.query.filter_by(name=user_name).first()
    user_id = user.id if user else None

    is_admin = user and user.name == "Suhail"  # Set is_admin based on user

    # Organize episodes by season and include average and user ratings
    episodes_by_season = {}
    for episode in tv_show.episodes:
        season = episode.season_number
        if season not in episodes_by_season:
            episodes_by_season[season] = []

        # Calculate the average rating for the episode
        average_rating = db.session.query(db.func.avg(EpisodeRating.rating)).filter_by(episode_id=episode.id).scalar()
        episode.average_rating = round(average_rating, 1) if average_rating else None

        # Fetch the current user's rating for the episode, if available
        user_rating = EpisodeRating.query.filter_by(user_id=user_id, episode_id=episode.id).first()
        episode.user_rating = user_rating.rating if user_rating else None

        episodes_by_season[season].append(episode)

    return render_template(
        'tv_show_details.html',
        tv_show=tv_show,
        episodes_by_season=episodes_by_season,
        is_admin=is_admin,
        user_name=user_name
    )

@app.route('/rate_episode', methods=['POST'])
def rate_episode():
    # Try to get user_name from URL arguments or session
    user_name = request.args.get('user_name') or session.get('user_name')
    episode_id = request.args.get('episode_id')
    rating = request.form.get('rating')

    # Validate user and rating input
    if not user_name or not episode_id or not rating:
        flash("Missing episode ID, user name, or rating.", "error")
        return redirect(url_for('dashboard', user_name=user_name))

    # Fetch user and episode details
    user = User.query.filter_by(name=user_name).first()
    episode = Episode.query.get(episode_id)
    if not user or not episode:
        flash("User or episode not found.", "error")
        return redirect(url_for('dashboard', user_name=user_name))

    # Process the rating
    rating_value = round(float(rating), 1)
    existing_rating = EpisodeRating.query.filter_by(user_id=user.id, episode_id=episode_id).first()

    if existing_rating:
        existing_rating.rating = rating_value
        flash("Your rating has been updated successfully!", "success")
    else:
        new_rating = EpisodeRating(user_id=user.id, episode_id=episode_id, rating=rating_value)
        db.session.add(new_rating)
        flash("Your rating has been submitted successfully!", "success")

    db.session.commit()

    # Redirect back to the dashboard with user_name
    return redirect(url_for('dashboard', user_name=user_name))


@app.route('/mark_episode_attendance', methods=['POST'])
def mark_episode_attendance():
    user_id = request.form.get('user_id')
    episode_id = request.form.get('episode_id')
    attended = request.form.get('attended') == 'on'

    # Check if attendance already exists
    existing_attendance = EpisodeAttendance.query.filter_by(user_id=user_id, episode_id=episode_id).first()
    if attended and not existing_attendance:
        # Add new attendance record
        new_attendance = EpisodeAttendance(user_id=user_id, episode_id=episode_id)
        db.session.add(new_attendance)
    elif not attended and existing_attendance:
        # Remove attendance record
        db.session.delete(existing_attendance)

    db.session.commit()
    flash("Attendance updated successfully!", "success")
    return redirect(url_for('episode_details', episode_id=episode_id))

@app.route('/episode_details/<int:episode_id>')
def episode_details(episode_id):
    episode = Episode.query.get_or_404(episode_id)
    
    # Calculate average rating
    average_rating = db.session.query(db.func.avg(EpisodeRating.rating)).filter_by(episode_id=episode.id).scalar()
    average_rating = round(average_rating, 1) if average_rating else None

    # Fetch user ratings for the episode, filtering out ratings without a valid user
    user_ratings = [
        {"user_name": rating.user.name, "rating": rating.rating}
        for rating in EpisodeRating.query.filter_by(episode_id=episode.id).all()
        if rating.user is not None
    ]

    return {
        "title": episode.title,
        "season_number": episode.season_number,
        "episode_number": episode.episode_number,
        "air_date": episode.air_date.strftime('%Y-%m-%d') if episode.air_date else "N/A",
        "runtime": episode.runtime,
        "average_rating": average_rating,
        "user_ratings": user_ratings
    }
@app.route('/toggle_episode_watched/<int:episode_id>', methods=['POST'])
def toggle_episode_watched(episode_id):
    episode = Episode.query.get_or_404(episode_id)
    # Assuming we add a "watched" boolean column to Episode to track its watched status
    episode.watched = not episode.watched  # Toggle the watched status
    db.session.commit()
    
    # Redirect back to the episode's details page or return a JSON response for AJAX updates
    flash(f"Episode marked as {'watched' if episode.watched else 'unwatched'}.", "success")
    return redirect(url_for('tv_show_details', show_id=episode.tv_show_id))

@app.route('/mark_as_watched/<int:episode_id>', methods=['POST'])
def mark_as_watched(episode_id):
    episode = db.session.get(Episode, episode_id)
    if episode:
        episode.watch_date = datetime.now(timezone.utc) if episode.watch_date is None else None
        print(f"marked episode {episode} as watched.")
        db.session.commit()
    return redirect(url_for('tv_show_details', show_id=episode.tv_show_id, user_name=session.get('user_name')))

@app.route('/edit_episode_attendance/<int:episode_id>', methods=['GET', 'POST'])
def admin_edit_episode_attendance(episode_id):
    episode = db.session.get(Episode, episode_id)
    users = User.query.all()  # Fetch all users
    
    if request.method == 'POST':
        # Update the attendance based on the selected users
        selected_user_ids = request.form.getlist('users')
        
        # Clear current attendance for the episode
        episode.attendance.delete()  # Remove all attendance records for this episode

        # Add selected users as attendees
        for user_id in selected_user_ids:
            user = db.session.get(User, int(user_id))
            if user:
                attendance_record = EpisodeAttendance(episode=episode, user=user)
                db.session.add(attendance_record)
        
        db.session.commit()
        
        # Redirect back to the tv_show_details page
        return redirect(url_for('tv_show_details', show_id=episode.tv_show_id, user_name=session.get('user_name')))
    # GET request: Render the form with the current attendance data
    attended_users = [attendance.user.id for attendance in episode.attendance]  # Access 'attendance' here
    return render_template('edit_episode_attendance.html', episode=episode, users=users, attended_users=attended_users)


############################################

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)
