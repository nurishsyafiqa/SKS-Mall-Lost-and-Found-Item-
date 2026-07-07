# security.py - Security functions for Lost & Found System

import re
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps
from flask import request, session, abort, current_app

# ========== Password Strength Checker ==========
def is_strong_password(password):
    """Check if password meets security requirements"""
    errors = []
    
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    if not re.search(r'[0-9]', password):
        errors.append("Password must contain at least one number")
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character")
    
    return len(errors) == 0, errors

# ========== Login Rate Limiting ==========
failed_attempts = defaultdict(list)

def is_rate_limited(identifier):
    """Check if user is rate limited due to too many failed attempts"""
    now = datetime.now()
    
    # Clean old attempts (older than 15 minutes)
    failed_attempts[identifier] = [
        attempt for attempt in failed_attempts[identifier]
        if now - attempt < timedelta(minutes=15)
    ]
    
    # Block after 5 failed attempts
    if len(failed_attempts[identifier]) >= 5:
        return True, 5
    
    return False, 5 - len(failed_attempts[identifier])

def record_failed_attempt(identifier):
    """Record a failed login attempt"""
    failed_attempts[identifier].append(datetime.now())

def clear_failed_attempts(identifier):
    """Clear failed attempts after successful login"""
    if identifier in failed_attempts:
        del failed_attempts[identifier]

# ========== Input Sanitization ==========
def sanitize_input(text):
    """Remove potentially dangerous characters from user input"""
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove JavaScript event handlers
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    
    # Remove script tags
    text = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', text, flags=re.IGNORECASE)
    
    # Remove special characters that could be used in injection
    text = re.sub(r'[<>\"\'&;`]', '', text)
    
    return text.strip()

def sanitize_form_data(form_data, fields):
    """Sanitize multiple form fields at once"""
    result = {}
    for field in fields:
        if field in form_data:
            result[field] = sanitize_input(form_data[field])
        else:
            result[field] = ""
    return result

# ========== CSRF Protection ==========
import secrets

def generate_csrf_token():
    """Generate a CSRF token for forms"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf_token():
    """Validate CSRF token from form submission"""
    form_token = request.form.get('csrf_token')
    session_token = session.get('csrf_token')
    
    if not form_token or not session_token:
        return False
    
    return secrets.compare_digest(form_token, session_token)

def csrf_protected(f):
    """Decorator to protect routes with CSRF check"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            if not validate_csrf_token():
                abort(403, "CSRF token validation failed")
        return f(*args, **kwargs)
    return decorated_function

# ========== Session Security ==========
def setup_secure_session(app):
    """Configure secure session settings"""
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# ========== SQL Injection Prevention Helper ==========
def validate_item_data(data):
    """Validate item data before database insertion"""
    errors = []
    
    if not data.get('category') or len(data['category']) < 2:
        errors.append("Category must be at least 2 characters")
    
    if not data.get('description') or len(data['description']) < 5:
        errors.append("Description must be at least 5 characters")
    
    if len(data.get('description', '')) > 500:
        errors.append("Description is too long (max 500 characters)")
    
    if not data.get('location') or len(data['location']) < 2:
        errors.append("Location must be at least 2 characters")
    
    if data.get('phone') and not re.match(r'^[\d\-+\s()]{8,20}$', data['phone']):
        errors.append("Invalid phone number format")
    
    if data.get('email') and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', data['email']):
        errors.append("Invalid email format")
    
    return errors

# ========== Admin Required Decorator with Extra Security ==========
def admin_secure(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            abort(401, "Authentication required")
        if session.get('role') != 'admin':
            abort(403, "Admin access required")
        
        # Log admin access
        from db_config import get_db_connection
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO activity_log (user_id, action, details, ip_address)
                    VALUES (%s, %s, %s, %s)
                """, (session['user_id'], 'admin_access', request.path, request.remote_addr))
                conn.commit()
            except:
                pass
            finally:
                cursor.close()
                conn.close()
        
        return f(*args, **kwargs)
    return decorated_function