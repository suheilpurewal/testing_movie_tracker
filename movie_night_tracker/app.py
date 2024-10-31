from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime

app = Flask(__name__)

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////data/users.db'
db = SQLAlchemy(app)

# Define a User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    ratings = db.relationship('Rating', cascade="all, delete", passive_deletes=True)
    attendance = db.relationship('MovieAttendance', cascade="all, delete", passive_deletes=True)

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    watch_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    attendance = db.relationship('MovieAttendance', backref='movie', lazy=True, cascade="all, delete-orphan")
    ratings = db.relationship('Rating', backref='movie_ref', lazy=True, cascade="all, delete-orphan")

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id', ondelete='CASCADE'), nullable=False)
    rating = db.Column(db.Float, nullable=False)

class MovieAttendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

class MovieRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    movie_title = db.Column(db.String(100), nullable=False)
    requested_by = db.Column(db.String(80), nullable=False)
    request_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    votes = db.Column(db.Integer, default=0)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(80), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey('movie_request.id'), nullable=False)
    vote_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    request = db.relationship('MovieRequest', backref=db.backref('votes_list', lazy=True))

# Create the database tables within an application context
with app.app_context():
    db.create_all()

    # Add "Suhail" as a default user if not exists
    suhail_user = User.query.filter_by(name="Suhail").first()
    if not suhail_user:
        suhail_user = User(name="Suhail")
        db.session.add(suhail_user)
        db.session.commit()

@app.route('/')
def home():
    users = User.query.all()
    return render_template('checkin.html', users=users)

@app.route('/dashboard')
def dashboard():
    user_name = request.args.get('user_name')
    view = request.args.get('view', 'all')  # Default view is 'all'

    movie_requests = MovieRequest.query.order_by(MovieRequest.votes.desc()).all()
    user = User.query.filter_by(name=user_name).first()
    movies = []
    unrated_movies = []

    if user:
        # Get all movies the user has attended
        attended_movie_titles = [attendance.movie.title for attendance in MovieAttendance.query.filter_by(user_id=user.id).all()]
        # Get all movies the user has reviewed
        rated_movie_titles = [rating.movie_ref.title for rating in user.ratings]
        unrated_movies = db.session.query(Movie).filter(
            Movie.title.in_(attended_movie_titles),
            ~Movie.title.in_(rated_movie_titles)
        ).all()
    
        if view == 'all':
            # Query all movies and their average ratings
            movies = db.session.query(
                Movie.id,
                Movie.title,
                Movie.watch_date,
                func.round(func.avg(Rating.rating), 1).label('average_rating')
            ).outerjoin(Rating).group_by(Movie.id).all()
        elif view == 'personal':
            # Get all movies the user has reviewed, including title and watch_date
            movies = db.session.query(
                Movie.id,
                Movie.title,
                Movie.watch_date,
                Rating.rating
            ).join(Rating).filter(Rating.user_id == user.id).all()

    return render_template('dashboard.html', user_name=user_name, view=view, movies=movies, unrated_movies=unrated_movies, movie_requests=movie_requests)

@app.route('/edit_attendance/<int:movie_id>', methods=['GET', 'POST'])
def edit_attendance(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    users = User.query.all()
    attended_users = [attendance.user_id for attendance in movie.attendance]

    # Capture user_name, defaulting to 'Suhail' if None
    user_name = request.form.get('user_name') or request.args.get('user_name') or "Suhail"
    print(f"User name on page load: {user_name}")

    if request.method == 'POST':
        # Capture all form data
        form_data = request.form.to_dict()
        print(f"Form data: {form_data}")

        # Capture user_name explicitly
        user_name = request.form.get('user_name') or "Suhail"  # Default to 'Suhail' if None
        print(f"User name on form submission: {user_name}")

        if not user_name:
            print("User name is missing!")
            return "User name is missing!", 400

        # Process the form submission here
        selected_user_ids = request.form.getlist('users')

        # Update the attendance in the database
        MovieAttendance.query.filter_by(movie_id=movie_id).delete()
        for user_id in selected_user_ids:
            new_attendance = MovieAttendance(movie_id=movie_id, user_id=user_id)
            db.session.add(new_attendance)
        db.session.commit()

        # Redirect back to the dashboard with the correct user_name
        return redirect(url_for('dashboard', user_name=user_name))

    return render_template('edit_attendance.html', movie=movie, users=users, attended_users=attended_users, user_name=user_name)

@app.route('/update_attendance/<int:movie_id>', methods=['POST'])
def update_attendance(movie_id):
    try:
        user_name = request.form.get('user_name')  # Retrieve the user_name from the form
        print(f"User name after submission: {user_name}")
        
        # Get the list of user IDs from the form submission
        user_ids = request.form.getlist('users')
        
        # Clear existing attendance records for this movie
        MovieAttendance.query.filter_by(movie_id=movie_id).delete()

        # Add the new attendance records
        for user_id in user_ids:
            attendance = MovieAttendance(user_id=user_id, movie_id=movie_id)
            db.session.add(attendance)
        
        db.session.commit()

        return redirect(url_for('dashboard', user_name=user_name))
    except Exception as e:
        print("Error updating attendance:", e)
        return str(e), 400  # Returning a 400 with the exception message

@app.route('/rate_movie', methods=['POST'])
def rate_movie():
    user_name = request.form.get('user_name')
    movie_title = request.form.get('movie')
    rating = round(float(request.form.get('rating')), 1)
    user = User.query.filter_by(name=user_name).first()
    movie = Movie.query.filter_by(title=movie_title).first()

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

    return redirect(url_for('dashboard', user_name=user_name))

@app.route('/movie/<movie_name>')
def movie_detail(movie_name):
    user_name = request.args.get('user_name')
    
    # Find the movie by title
    movie = Movie.query.filter_by(title=movie_name).first_or_404()
    
    # Get all ratings for this movie, joining with the User table to get user details
    ratings = db.session.query(Rating, User).join(User, Rating.user_id == User.id).filter(Rating.movie_id == movie.id).all()
    
    return render_template('movie_detail.html', movie_name=movie_name, ratings=ratings, user_name=user_name)

@app.route('/request_movie', methods=['GET', 'POST'])
def request_movie():
    if request.method == 'POST':
        movie_title = request.form['movie_title']
        requested_by = request.form['requested_by']
        existing_request = MovieRequest.query.filter_by(movie_title=movie_title).first()
        if existing_request:
            return redirect(url_for('request_movie', message="Movie already requested!"))

        new_request = MovieRequest(movie_title=movie_title, requested_by=requested_by)
        db.session.add(new_request)
        db.session.commit()

        return redirect(url_for('dashboard', user_name=requested_by))

    message = request.args.get('message')
    users = User.query.all()
    return render_template('request_movie.html', message=message, users=users)

@app.route('/vote_movie/<int:request_id>', methods=['POST'])
def vote_movie(request_id):
    user_name = request.form['user_name']
    existing_vote = Vote.query.filter_by(user_name=user_name, request_id=request_id).first()
    if existing_vote:
        return redirect(url_for('dashboard', user_name=user_name, message="You have already voted for this request."))

    movie_request = MovieRequest.query.get(request_id)
    if movie_request:
        movie_request.votes += 1
        new_vote = Vote(user_name=user_name, request_id=request_id)
        db.session.add(new_vote)
        db.session.commit()

    return redirect(url_for('dashboard', user_name=user_name))

@app.route('/delete_request/<int:request_id>', methods=['POST'])
def delete_request(request_id):
    user_name = request.form['user_name']
    if user_name == "Suhail":
        # Delete all votes associated with the request
        votes = Vote.query.filter_by(request_id=request_id).all()
        for vote in votes:
            db.session.delete(vote)
        
        # Now delete the movie request
        movie_request = MovieRequest.query.get(request_id)
        if movie_request:
            db.session.delete(movie_request)
            db.session.commit()
            
    return redirect(url_for('dashboard', user_name=user_name))

@app.route('/checkin', methods=['POST'])
def checkin():
    try:
        user_name = request.form.get('name') or request.form.get('new_name')

        if not user_name:
            raise ValueError("User name is required.")

        user = User.query.filter_by(name=user_name).first()
        if not user:
            user = User(name=user_name)
            db.session.add(user)
            db.session.commit()

        return redirect(url_for('dashboard', user_name=user_name))
    except Exception as e:
        print(f"Error during check-in: {e}")  # Log the error
        return str(e), 400


@app.route('/add_movie', methods=['POST'])
def add_movie():
    user_name = request.form['user_name']
    movie_title = request.form['movie']

    if user_name == "Suhail":
        new_movie = Movie(title=movie_title, watch_date=datetime.utcnow())
        db.session.add(new_movie)
        db.session.commit()

    return redirect(url_for('dashboard', user_name=user_name))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    user_name = request.args.get('user_name')
    if user_name != "Suhail":
        return redirect(url_for('dashboard', user_name=user_name))
    
    if request.method == 'POST':
        new_user_name = request.form.get('new_user_name')
        if new_user_name:
            existing_user = User.query.filter_by(name=new_user_name).first()
            if not existing_user:
                new_user = User(name=new_user_name)
                db.session.add(new_user)
                db.session.commit()
    
    users = User.query.all()
    movies = Movie.query.all()  # Ensure this line is included
    return render_template('admin.html', users=users, movies=movies, user_name=user_name)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    user_name = request.form.get('user_name')
    
    # Fetch the user to be deleted
    user_to_delete = User.query.get_or_404(user_id)
    
    # Delete the user along with associated ratings and attendance
    if user_to_delete:
        db.session.delete(user_to_delete)
        db.session.commit()
    
    # Redirect back to the admin page with the current user_name
    return redirect(url_for('admin', user_name=user_name))

@app.route('/delete_movie/<int:movie_id>', methods=['POST'])
def delete_movie(movie_id):
    user_name = request.form.get('user_name')  # Retrieve user_name from the form
    if user_name != "Suhail":
        return redirect(url_for('dashboard', user_name=user_name))
    
    movie = Movie.query.get_or_404(movie_id)
    db.session.delete(movie)
    db.session.commit()
    
    return redirect(url_for('admin', user_name=user_name))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)