from passlib.hash import pbkdf2_sha256

class User:
    def __init__(self, username, email, password, profile_image_path):
        self.username = username
        self.email = email
        self.password = password
        self.profile_image_path = profile_image_path

    @staticmethod
    def is_authenticated(self):
        return True
    
    @staticmethod
    def is_active(self):
        return True
    
    @staticmethod
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return self.username
    
    def verify_password(self, password_input):
        return pbkdf2_sha256.verify(password_input, self.password)
        