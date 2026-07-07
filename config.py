import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ===== SQLite Configuration (for Render) =====
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-secret-key')
    
    # ===== SQLite Database Path =====
    DATABASE = os.getenv('DATABASE', 'sks_mall.db')
    
    # ===== Keep for reference (but not used) =====
    # MySQL config (commented out for Render)
    # MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    # MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    # MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    # MYSQL_DB = os.getenv('MYSQL_DB', 'mall_lost_found')
    # MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
