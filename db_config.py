import sqlite3
import bcrypt
import os

# Database file path
DB_PATH = '/tmp/sks_mall.db'

def get_db_connection():
    """Create and return a SQLite database connection"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Error connecting to SQLite: {e}")
        return None

def hash_password(password):
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def check_password(password, hashed):
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))