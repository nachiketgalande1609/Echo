from datetime import datetime
from bson.json_util import dumps
from flask_login import LoginManager, current_user, login_user, login_required, logout_user
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_socketio import SocketIO, join_room, leave_room
import database
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = 'dsd1jhb18e7h'
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins='*')
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@app.route('/')
def landing_page():
    return render_template('landing_page.html')

# Home Page
@app.route('/home/', methods=['GET','POST'])
@login_required
def home():
    # Create Room code
    if request.method == 'POST':
        message = ''
        room_name = request.form.get('room_name')
        usernames = [username.strip() for username in request.form.get('members').split(',')]
        if len(room_name) and len(usernames):
            room_id = database.save_room(room_name, current_user.username)
            if current_user.username in usernames:
                usernames.remove(current_user.username)
            database.add_room_members(room_id, room_name, usernames, current_user.username)
            return redirect(url_for('home'))
        else:
            message = 'Failed to create room'
            return render_template('home.html', message=message)
        
    # Fetch rooms for user
    rooms = []
    rooms = database.get_rooms_for_user(current_user.username)
    return render_template('home.html', rooms=rooms)

# Chat Page
@app.route('/rooms/<room_id>')
@login_required
def view_room(room_id):
    room = database.get_room(room_id)
    if room and database.is_room_member(room_id, current_user.username):
        room_members = database.get_room_members(room_id)
        messages = database.get_messages(room_id)
        return render_template('view_room.html', username=current_user.username, room=room, room_members=room_members, messages=messages)
    else:
        return "Room Not Found", 404

# Get older messages
@app.route('/rooms/<room_id>/messages/')
@login_required
def get_older_messages(room_id):
    room = database.get_room(room_id)
    if room and database.is_room_member(room_id, current_user.username):
        page = int(request.args.get('page', 0))
        messages = database.get_messages(room_id, page)
        return dumps(messages)
    else:
        return "Room Not Found", 404

# Edit Room
@app.route('/rooms/<room_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_room(room_id):
    room = database.get_room(room_id)
    if room and database.is_room_admin(room_id, current_user.username):
        message = ''
        existing_room_members = [member['_id']['username'] for member in database.get_room_members(room_id)]
        room_members_str = ",".join(existing_room_members)
        if request.method == 'POST':
            room_name = request.form.get('room_name')
            room['name'] = room_name
            database.update_room(room_id, room_name)
            new_members = [username.strip() for username in request.form.get('members').split(',')]
            members_to_add = list(set(new_members) - set(existing_room_members))
            members_to_remove = list(set(existing_room_members) - set(new_members))
            if len(members_to_add):
                database.add_room_members(room_id, room_name, members_to_add, current_user.username)
            if len(members_to_remove):
                database.remove_room_members(room_id, members_to_remove)
            room_members_str = ",".join(new_members)
            return redirect(url_for('view_room', room_id=room_id))
        return render_template('edit_room.html', room_members_str=room_members_str, message=message, room_id=room_id)
    else:
        return "Room Not Found", 404    
    
@app.route('/delete_room/<room_id>', methods=['GET', 'POST'])
@login_required
def delete_room(room_id):
    database.delete_room(room_id)
    return render_template('home.html')    

@app.route('/search_users')
def search_users():
    query = request.args.get('q')  # Get the typed query from the request
    users = database.search_users(query)
    return jsonify(users)

# Signup
@app.route('/signup/', methods=['GET','POST'])
def signup():
    from database import db
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    message = ''
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password_input = request.form.get('password')

        user = db.users.find_one({'_id': username})
        if user:
            message = 'User already exists'
        else:
            database.save_user(username, email, password_input)
            return redirect(url_for('login'))
    return render_template('signup.html', message=message)

# Login
@app.route('/login/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    message = ''
    if request.method == 'POST':
        username = request.form.get('username')
        password_input = request.form.get('password')

        user = database.get_user(username)
        print(user)
        if user and user.verify_password(password_input):
            login_user(user)
            return redirect(url_for('home'))
        else:
            message = 'Login failed'
    return render_template('login.html', message=message)

# Logout
@app.route('/logout/')
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing_page'))

# Account Page
@app.route('/account')
def account():
    user = database.get_user(current_user.username)
    return render_template('account.html', user=user)

# Edit Account and Profile Picture
@app.route('/edit_account', methods=['GET', 'POST'])
def edit_account():
    UPLOAD_FOLDER = '../static/profile_images'
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    from database import db
    user = database.get_user(current_user.username)
    if request.method == 'POST':
        profile_image_file = request.files['profileimage']
        if profile_image_file:
            profile_image_filename = secure_filename(profile_image_file.filename)
            profile_image_path = os.path.join('static', 'profile_images', profile_image_filename)
            profile_image_file.save(profile_image_path)
            db.users.update_one({'_id': current_user.username}, {'$set': {'profile_image_path': profile_image_path}})
            return redirect(url_for('account'))
    return render_template('edit_account.html', user=user)

# Socket routes #######################################################################################

@socketio.on('join_room')
def handle_join_room_event(data):
    app.logger.info("{} has joined the room {}".format(data['username'], data['room']))
    join_room(data['room'])
    socketio.emit('join_room_announcement', data)

@socketio.on('leave_room')
def handle_leave_room_event(data):
    app.logger.info("{} has left the room {}".format(data['username'], data['room']))
    leave_room(data['room'])
    socketio.emit('leave_room_announcement', data, room=data['room'])

@socketio.on('send_message')
def handle_send_message_event(data):
    from database import db
    app.logger.info("{} has sent message to the room {}: {}".format(data['username'], data['room'], data['message']))
    data['created_at'] = datetime.now().strftime("%d %b, %H:%M")
    user = db.users.find_one({'_id': data['username']})
    data['profile_image_path'] = user['profile_image_path']
    database.save_message(data['room'], data['message'], data['username'], user['profile_image_path'])
    socketio.emit('receive_message', data, room=data['room'])

@login_manager.user_loader
def load_user(username):
    return database.get_user(username)

# #####################################################################################################

if __name__=='__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
    # socketio.run(app, debug=True)