from user.models import User
from pymongo import DESCENDING, MongoClient
from passlib.hash import pbkdf2_sha256
from user.models import User
from datetime import datetime
from bson import ObjectId
import re

client=MongoClient("mongodb://localhost:27017/")
db = client.echo

# Save user details on signup
def save_user(username, email, password):
    db.users.insert_one({'_id': username, 'email': email, 'password': pbkdf2_sha256.hash(password), 'profile_image_path': 'static\profile_images\dflt.jpg'})
    print("User inserted")

# Get user dateils for the user
def get_user(username):
    user_data = db.users.find_one({'_id': username})
    return User(user_data['_id'], user_data['email'], user_data['password'], user_data['profile_image_path']) if user_data else None

# Save room details while creating room
def save_room(room_name, created_by):
    room_id = db.rooms.insert_one(
        {'name': room_name, 'created_by': created_by, 'created_at': datetime.now()}).inserted_id
    add_room_member(room_id, room_name, created_by, created_by, is_room_admin=True)
    return room_id

# Update room details while editing room
def update_room(room_id, room_name):
    db.rooms.update_one({'_id': ObjectId(room_id)}, {'$set': {'name': room_name}})
    db.room_members.update_many({'_id.room_id': ObjectId(room_id)}, {'$set': {'room_name': room_name}})

# Get room details by passing the room_id
def get_room(room_id):
    return db.rooms.find_one({'_id': ObjectId(room_id)})

def delete_room(room_id):
    db.rooms.delete_one({'_id': ObjectId(room_id)})
    db.room_members.delete_many({'_id.room_id': ObjectId(room_id)})

# Add rooom member while creating room
def add_room_member(room_id, room_name, username, added_by, is_room_admin=False):
    db.room_members.insert_one(
        {'_id': {'room_id': ObjectId(room_id), 'username': username}, 'room_name': room_name, 'added_by': added_by,
         'added_at': datetime.now(), 'is_room_admin': is_room_admin})

# Add room members while editin room
def add_room_members(room_id, room_name, usernames, added_by):
    if usernames:  # Check if usernames list is not empty
        documents = [{'_id': {'room_id': ObjectId(room_id), 'username': username},
                      'room_name': room_name,
                      'added_by': added_by,
                      'added_at': datetime.now(),
                      'is_room_admin': False} for username in usernames]

        if documents:  # Ensure documents list is not empty
            db.room_members.insert_many(documents)
        else:
            print("Documents list is empty.")
    else:
        print("Usernames list is empty.")

# Remove room members while editing room
def remove_room_members(room_id, usernames):
    db.room_members.delete_many(
        {'_id': {'$in': [{'room_id': ObjectId(room_id), 'username': username} for username in usernames]}})

# Get users of the rooms
def get_room_members(room_id):
    return list(db.room_members.find({'_id.room_id': ObjectId(room_id)}))

# Get rooms for the user
def get_rooms_for_user(username):
    return list(db.room_members.find({'_id.username': username}))

# ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def get_users_for_room(room_id):
    return list(db.room_members.aggregate([{'$match': { "_id.room_id": room_id }},{'$group': { '_id': "$_id.room_id", 'usernames': { '$push': "$_id.username" } } }]))
# ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

# Check if user is a member of the room
def is_room_member(room_id, username):
    return db.room_members.count_documents({'_id': {'room_id': ObjectId(room_id), 'username': username}})

# Check if user is an admin of the room
def is_room_admin(room_id, username):
    return db.room_members.count_documents(
        {'_id': {'room_id': ObjectId(room_id), 'username': username}, 'is_room_admin': True})

# Save user message to DB
def save_message(room_id, text, sender, profile_image_path):
    db.messages.insert_one({'room_id': room_id, 'text': text, 'sender': sender, 'created_at': datetime.now(), 'profile_image_path':profile_image_path})

def search_users(query):
    pattern = re.compile(query, re.IGNORECASE)
    matching_users = db.users.find({'_id': {'$regex': pattern}})
    users_list = list(matching_users)
    return users_list

# Get room messages
MESSAGE_FETCH_LIMIT = 3

def get_messages(room_id, page=0):
    offset = page * MESSAGE_FETCH_LIMIT
    messages = list(db.messages.find({'room_id': room_id}).sort('_id', DESCENDING).limit(MESSAGE_FETCH_LIMIT).skip(offset))
    for message in messages:
        message['created_at'] = message['created_at'].strftime("%d %b, %H:%M")
    return messages[::-1]