import mysql.connector
from mysql.connector import Error
from config import Config
import bcrypt

def get_db_connection():
    """Create and return a MySQL database connection"""
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            port=Config.MYSQL_PORT
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def hash_password(password):
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def check_password(password, hashed):
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def setup_admin_user():
    """Create proper admin user with hashed password"""
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        hashed_pw = hash_password('admin123')
        cursor.execute("UPDATE users SET password_hash = %s WHERE username = 'admin'", (hashed_pw,))
        conn.commit()
        print("✅ Admin user configured! Username: admin, Password: admin123")
        cursor.close()
        conn.close()

# Test connection
if __name__ == "__main__":
    conn = get_db_connection()
    if conn:
        print("✅ Connected to MySQL successfully!")
        setup_admin_user()
        conn.close()
    else:
        print("❌ Failed to connect. Check your MySQL credentials in .env file")