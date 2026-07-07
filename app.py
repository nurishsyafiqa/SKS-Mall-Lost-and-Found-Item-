from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from db_config import get_db_connection, check_password, hash_password
from config import Config
from datetime import date, datetime, timedelta
from functools import wraps
import difflib
import re
import secrets
from collections import defaultdict
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
import qrcode
import io
import base64

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# ========== Security Configuration ==========
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
app.config['PERMANENT_SESSION_LIFETIME'] = int(os.getenv('PERMANENT_SESSION_LIFETIME', 30)) * 60

# ========== SECURITY HEADERS ==========
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# ========== BASE URL CONFIGURATION ==========
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')

print("=" * 50)
print("🌐 BASE URL CONFIGURATION:")
print(f"   Base URL: {BASE_URL}")
print("=" * 50)

# ========== EMAIL CONFIGURATION FROM .ENV ==========
EMAIL_HOST = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('MAIL_PORT', 587))
EMAIL_USER = os.getenv('MAIL_USERNAME', '')
EMAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
EMAIL_FROM = os.getenv('MAIL_DEFAULT_SENDER', 'SKS Mall Lost & Found')
EMAIL_ENABLED = os.getenv('MAIL_ENABLED', 'False').lower() == 'true'

print("=" * 50)
print("📧 EMAIL CONFIGURATION:")
print(f"   Host: {EMAIL_HOST}")
print(f"   Port: {EMAIL_PORT}")
print(f"   User: {EMAIL_USER}")
print(f"   Password length: {len(EMAIL_PASSWORD) if EMAIL_PASSWORD else 0}")
print(f"   Enabled: {EMAIL_ENABLED}")
print("=" * 50)

# ========== QR CODE GENERATION ==========
def generate_claim_qr(claim_id, item_id=None):
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        base_url = BASE_URL
        if item_id:
            track_url = f"{base_url}/claim-item?item_id={item_id}"
        else:
            track_url = f"{base_url}/track-claim?claim_id={claim_id}"
        qr.add_data(track_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#4A148C", back_color="white")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return img_str
    except Exception as e:
        print(f"QR Error: {e}")
        return None

def generate_claim_qr_for_page(page_url):
    try:
        qr = qrcode.QRCode(version=1, box_size=12, border=4)
        qr.add_data(page_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#4A148C", back_color="white")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return img_str
    except Exception as e:
        print(f"QR Error: {e}")
        return None

# ========== EMAIL FUNCTIONS ==========
def send_real_email(to_email, subject, body_html):
    if not EMAIL_ENABLED:
        print("⚠️ Email sending is disabled. Set MAIL_ENABLED=True in .env to enable.")
        return False
    if not EMAIL_USER or not EMAIL_PASSWORD:
        print("❌ Email credentials not configured. Please check your .env file.")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body_html, 'html'))
        print(f"📧 Connecting to {EMAIL_HOST}:{EMAIL_PORT}...")
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        print(f"📧 Logging in as {EMAIL_USER}...")
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        print(f"📧 Sending email to {to_email}...")
        server.send_message(msg)
        server.quit()
        print(f"✅ Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False

def send_login_alert_email(to_email, username, device_info, ip_address):
    subject = f"🔐 New Login to SKS Mall System - {username}"
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
            <div style="background-color: #4A148C; color: white; padding: 10px; text-align: center; border-radius: 5px;">
                <h2>SKS Mall Lost & Found System</h2>
            </div>
            <h3>🔐 New Login Detected</h3>
            <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; border-left: 4px solid #ffc107;">
                <p><strong>⚠️ A new login was detected to your account:</strong></p>
                <p><strong>👤 Username:</strong> {username}</p>
                <p><strong>🖥️ Device:</strong> {device_info}</p>
                <p><strong>📍 IP Address:</strong> {ip_address}</p>
                <p><strong>🕐 Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            <p>If this was you, you can ignore this message.</p>
            <p><strong>If this was NOT you, please contact SKS Mall staff immediately!</strong></p>
            <hr>
            <div style="font-size: 12px; color: #666; text-align: center;">
                <p>SKS Mall Lost & Found | Level 1, Customer Service Counter</p>
            </div>
        </div>
    </body>
    </html>
    """
    if EMAIL_ENABLED:
        return send_real_email(to_email, subject, body_html)
    else:
        print("\n" + "="*60)
        print(f"🔐 LOGIN ALERT - New device detected!")
        print(f"   User: {username}")
        print(f"   Device: {device_info}")
        print(f"   IP: {ip_address}")
        print("="*60 + "\n")
        return True

def send_claim_confirmation_email(to_email, claimant_name, claim_id, item_details):
    subject = f"Your Claim ID: {claim_id} - SKS Mall Lost & Found"
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
            <div style="background-color: #4CAF50; color: white; padding: 10px; text-align: center; border-radius: 5px;">
                <h2>SKS Mall Lost & Found System</h2>
            </div>
            <h3>Dear {claimant_name},</h3>
            <p>Your claim has been successfully submitted to SKS Mall Lost & Found system.</p>
            <div style="background-color: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin: 0 0 10px 0;">Your Claim Details:</h3>
                <p><strong>📍 Claim ID:</strong> <span style="font-size: 24px; font-weight: bold; color: #2196F3;">{claim_id}</span></p>
                <p><strong>Item:</strong> {item_details.get('category', 'Unknown')}</p>
                <p><strong>Description:</strong> {item_details.get('description', 'N/A')[:100]}</p>
                <p><strong>Status:</strong> <span style="color: orange;">Pending Review</span></p>
            </div>
            <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3>⚠️ Important Information:</h3>
                <ul>
                    <li>Please <strong>save your Claim ID</strong> for future reference</li>
                    <li>SKS Mall staff will review your claim within 2-3 business days</li>
                    <li>You will receive another email when your claim is approved/rejected</li>
                    <li>Bring your Claim ID and IC/Passport when collecting your item at SKS Mall</li>
                </ul>
            </div>
            <p><a href="{BASE_URL}/track-claim">Click here to track your claim at SKS Mall</a></p>
            <hr>
            <div style="font-size: 12px; color: #666; text-align: center;">
                <p>SKS Mall Lost & Found | Level 1, Customer Service Counter</p>
            </div>
        </div>
    </body>
    </html>
    """
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO email_log (to_email, subject, body, claim_id, sent)
                VALUES (%s, %s, %s, %s, %s)
            """, (to_email, subject, body_html, claim_id, EMAIL_ENABLED))
            conn.commit()
        except Exception as e:
            print(f"Database log error (email_log may not exist): {e}")
        finally:
            cursor.close()
            conn.close()
    if EMAIL_ENABLED:
        return send_real_email(to_email, subject, body_html)
    else:
        print("\n" + "="*60)
        print(f"📧 DEMO MODE - EMAIL WOULD BE SENT TO: {to_email}")
        print(f"Subject: {subject}")
        print("-"*40)
        print(f"Dear {claimant_name},")
        print(f"\nYour Claim ID is: {claim_id}")
        print("="*60 + "\n")
        return True

def send_claim_status_email(to_email, claimant_name, claim_id, status, notes=""):
    if status == 'approved':
        status_text = "APPROVED ✅"
        status_color = "#4CAF50"
        message = "Your claim has been approved! You can now collect your item from SKS Mall."
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                <h2 style="color: {status_color};">Claim {status_text}</h2>
                <p>Dear {claimant_name},</p>
                <p>{message}</p>
                <div style="background-color: #d4edda; padding: 15px; border-radius: 5px;">
                    <h3>📦 To Collect Your Item at SKS Mall:</h3>
                    <ul>
                        <li>Bring your <strong>Claim ID: {claim_id}</strong></li>
                        <li>Bring your <strong>IC/Passport</strong> for verification</li>
                        <li>Visit SKS Mall Lost & Found Office at Level 1, Customer Service Counter</li>
                        <li>Operating Hours: 10:00 AM - 10:00 PM Daily</li>
                    </ul>
                </div>
                <p><a href="{BASE_URL}/track-claim">Track your claim status at SKS Mall</a></p>
                <hr>
                <p style="font-size: 12px; color: #666; text-align: center;">SKS Mall Lost & Found System</p>
            </div>
        </body>
        </html>
        """
        subject = f"Claim {claim_id} - {status_text}"
    else:
        status_text = "REJECTED ❌"
        status_color = "#f44336"
        message = "Your claim has been rejected. Please contact SKS Mall staff for more information."
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                <h2 style="color: {status_color};">Claim {status_text}</h2>
                <p>Dear {claimant_name},</p>
                <p>{message}</p>
                {f'<p><strong>Staff Notes:</strong> {notes}</p>' if notes else ''}
                <p>Please contact SKS Mall Lost & Found office for assistance.</p>
                <hr>
                <p style="font-size: 12px; color: #666; text-align: center;">SKS Mall Lost & Found System</p>
            </div>
        </body>
        </html>
        """
        subject = f"Claim {claim_id} - {status_text}"
    if EMAIL_ENABLED:
        return send_real_email(to_email, subject, body_html)
    else:
        print(f"\n📧 DEMO MODE - Status email to: {to_email} - {status_text}\n")
        return True

def generate_unique_claim_id(prefix, db_id):
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{str(db_id).zfill(4)}"

# ========== Navigation Security ==========
@app.before_request
def restrict_staff_access():
    restricted_prefixes = ['/staff/', '/admin/']
    for prefix in restricted_prefixes:
        if request.path.startswith(prefix):
            if not session.get('user_id'):
                flash('Please login as SKS Mall staff to access this page', 'warning')
                return redirect(url_for('login'))
    if request.path.startswith('/admin/'):
        if session.get('role') != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('index'))

# ========== Rate Limiting ==========
failed_attempts = defaultdict(list)

def is_rate_limited(identifier):
    now = datetime.now()
    failed_attempts[identifier] = [a for a in failed_attempts[identifier] if now - a < timedelta(minutes=15)]
    if len(failed_attempts[identifier]) >= 5:
        return True, 5
    return False, 5 - len(failed_attempts[identifier])

def record_failed_attempt(identifier):
    failed_attempts[identifier].append(datetime.now())

def clear_failed_attempts(identifier):
    if identifier in failed_attempts:
        del failed_attempts[identifier]

# ========== Input Sanitization ==========
def sanitize_input(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[<>\"\'&;`]', '', text)
    return text.strip()

def validate_item_data(category, description, location):
    errors = []
    if not category or len(category) < 2:
        errors.append("Category must be at least 2 characters")
    if not description or len(description) < 5:
        errors.append("Description must be at least 5 characters")
    if len(description) > 500:
        errors.append("Description is too long (max 500 characters)")
    if not location or len(location) < 2:
        errors.append("Location must be at least 2 characters")
    return errors

def is_strong_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    common_passwords = ['password', '123456', 'qwerty', 'admin', 'welcome', 'letmein', 'monkey', '12345678']
    if password.lower() in common_passwords:
        return False, "Password is too common. Please choose a stronger password."
    return True, "Password is strong"

# ========== CSRF Protection ==========
def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf_token():
    form_token = request.form.get('csrf_token')
    session_token = session.get('csrf_token')
    if not form_token or not session_token:
        return False
    return secrets.compare_digest(form_token, session_token)

def csrf_protected(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            if not validate_csrf_token():
                abort(403, "CSRF token validation failed")
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token())

# ========== Role-Based Access Control ==========
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        if session.get('role') not in ['admin', 'staff']:
            flash('Staff access required', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ========== FIXED MATCHING FUNCTION ==========
def find_matches(lost_item_id):
    conn = get_db_connection()
    cursor = conn.cursor()  # FIXED: removed dictionary=True
    
    cursor.execute("SELECT * FROM items WHERE id = %s", (lost_item_id,))
    lost_item = cursor.fetchone()
    
    if not lost_item:
        cursor.close()
        conn.close()
        return 0
    
    cursor.execute("SELECT * FROM items WHERE type = 'found' AND status = 'open'")
    found_items = cursor.fetchall()
    
    print(f"🔍 Searching matches for lost item #{lost_item_id}: {lost_item['category']}")
    print(f"   Found {len(found_items)} items to check")
    
    matches_count = 0
    
    for found in found_items:
        score = 0
        
        if lost_item['category'].lower() == found['category'].lower():
            score += 40
            print(f"   ✅ Category match: {lost_item['category']} == {found['category']}")
        
        if lost_item['color'] and found['color']:
            if lost_item['color'].lower() == found['color'].lower():
                score += 30
                print(f"   ✅ Color match: {lost_item['color']} == {found['color']}")
        
        if lost_item['brand'] and found['brand']:
            if lost_item['brand'].lower() == found['brand'].lower():
                score += 20
                print(f"   ✅ Brand match: {lost_item['brand']} == {found['brand']}")
        
        print(f"   Score: {score}")
        
        if score > 40:
            cursor.execute("""
                INSERT INTO matches (lost_item_id, found_item_id, match_score, status)
                VALUES (%s, %s, %s, 'pending')
            """, (lost_item_id, found['id'], score))
            conn.commit()
            matches_count += 1
            print(f"   ✅ MATCH FOUND! Score: {score}")
        else:
            print(f"   ❌ No match (score {score} <= 40)")
    
    cursor.close()
    conn.close()
    print(f"✅ Total matches found: {matches_count}")
    return matches_count

def log_activity(user_id, action, details=""):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO activity_log (user_id, action, details, ip_address)
            VALUES (%s, %s, %s, %s)
        """, (user_id, action, details, request.remote_addr))
        conn.commit()
    except:
        pass
    finally:
        cursor.close()
        conn.close()

# ========== Public Routes ==========
@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()  # FIXED: removed dictionary=True
    cursor.execute("""
        SELECT * FROM items 
        WHERE status != 'archived' 
        ORDER BY date_reported DESC 
        LIMIT 10
    """)
    recent_items = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) as total FROM items WHERE status != 'archived'")
    total = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as open FROM items WHERE status = 'open'")
    open_cases = cursor.fetchone()['open']
    cursor.execute("SELECT COUNT(*) as found FROM items WHERE type = 'found' AND status != 'archived'")
    found_count = cursor.fetchone()['found']
    cursor.execute("SELECT COUNT(*) as lost FROM items WHERE type = 'lost' AND status != 'archived'")
    lost_count = cursor.fetchone()['lost']
    cursor.execute("SELECT COUNT(*) as claimed FROM items WHERE status = 'claimed'")
    claimed_count = cursor.fetchone()['claimed']
    cursor.close()
    conn.close()
    return render_template('index.html', 
                         recent_items=recent_items, 
                         total=total, 
                         open_cases=open_cases,
                         found_count=found_count,
                         lost_count=lost_count,
                         claimed_count=claimed_count)

@app.route('/test-email')
def test_email():
    print("\n🧪 TESTING EMAIL...")
    result = send_claim_confirmation_email(
        to_email='test@gmail.com',
        claimant_name='Test User',
        claim_id='TEST-001',
        item_details={'category': 'Test Item', 'description': 'This is a test email from SKS Mall Lost & Found System'}
    )
    if result:
        return """
        <div style='text-align:center; padding:50px; font-family:Arial;'>
            <h2 style='color:green;'>✅ Email sent successfully!</h2>
            <a href='/'>Back to Home</a>
        </div>
        """
    else:
        return """
        <div style='text-align:center; padding:50px; font-family:Arial;'>
            <h2 style='color:red;'>❌ Email failed to send</h2>
            <a href='/'>Back to Home</a>
        </div>
        """

# ========== UPDATED LOGIN ROUTE ==========
@app.route('/login', methods=['GET', 'POST'])
@csrf_protected
def login():
    if request.method == 'POST':
        username = sanitize_input(request.form['username'])
        password = request.form['password']
        
        limited, remaining = is_rate_limited(f'login_{username}')
        if limited:
            flash('Too many failed attempts. Please wait 15 minutes.', 'danger')
            return render_template('login.html')
        
        conn = get_db_connection()
        cursor = conn.cursor()  # FIXED: removed dictionary=True
        cursor.execute("SELECT * FROM users WHERE username = %s AND is_active = TRUE", (username,))
        user = cursor.fetchone()
        
        if user:
            if user.get('lockout_time') and user['lockout_time'] > datetime.now():
                remaining_lockout = (user['lockout_time'] - datetime.now()).seconds // 60
                flash(f'⛔ Account locked. Please try again in {remaining_lockout + 1} minutes.', 'danger')
                cursor.close()
                conn.close()
                return render_template('login.html')
        
        if user and check_password(password, user['password_hash']):
            cursor.execute("""
                UPDATE users 
                SET failed_login_attempts = 0, lockout_time = NULL
                WHERE id = %s
            """, (user['id'],))
            conn.commit()
            clear_failed_attempts(f'login_{username}')
            
            device_info = f"{request.user_agent} | {request.remote_addr}"
            known_devices = user.get('known_devices', '')
            is_new_device = device_info not in (known_devices or '')
            
            if is_new_device and user['role'] in ['admin', 'staff']:
                if user.get('email'):
                    send_login_alert_email(user['email'], username, device_info, request.remote_addr)
                    print(f"📧 Login alert sent to {user['email']}")
                
                new_devices = known_devices + "|" + device_info if known_devices else device_info
                cursor.execute("UPDATE users SET known_devices = %s WHERE id = %s", (new_devices, user['id']))
                conn.commit()
                flash('🔐 New device detected! A security alert has been sent to your email.', 'info')
            
            if request.form.get('remember'):
                session.permanent = True
                app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
            else:
                session.permanent = True
                app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
            
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user.get('full_name', username)
            session['ip_address'] = request.remote_addr
            session['last_active'] = datetime.now()
            
            log_activity(user['id'], 'login', f'User logged in from {request.remote_addr}')
            print(f"✅ Successful login: {username} from IP: {request.remote_addr}")
            
            flash(f'Welcome to SKS Mall, {user["full_name"]}!', 'success')
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('staff_dashboard'))
        
        else:
            if user:
                cursor.execute("""
                    UPDATE users 
                    SET failed_login_attempts = failed_login_attempts + 1
                    WHERE id = %s
                """, (user['id'],))
                
                cursor.execute("SELECT failed_login_attempts FROM users WHERE id = %s", (user['id'],))
                attempts = cursor.fetchone()
                
                if attempts and attempts['failed_login_attempts'] >= 5:
                    lockout_time = datetime.now() + timedelta(minutes=30)
                    cursor.execute("UPDATE users SET lockout_time = %s WHERE id = %s", (lockout_time, user['id']))
                    conn.commit()
                    flash(f'⛔ Too many failed attempts. Account locked for 30 minutes.', 'danger')
                    log_activity(user['id'], 'account_locked', f'Account locked after 5 failed attempts from {request.remote_addr}')
                    print(f"🔒 Account locked: {username} from IP: {request.remote_addr}")
                    cursor.close()
                    conn.close()
                    return render_template('login.html')
                
                conn.commit()
                log_activity(user['id'], 'failed_login', f'Failed login from {request.remote_addr}')
                print(f"⚠️ Failed login attempt: {username} from IP: {request.remote_addr}")
            
            record_failed_attempt(f'login_{username}')
            remaining_attempts = 5 - (user['failed_login_attempts'] if user else 0)
            if remaining_attempts > 0:
                flash(f'Invalid username or password. {remaining_attempts} attempts remaining.', 'danger')
            else:
                flash('Invalid username or password.', 'danger')
            
            cursor.close()
            conn.close()
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_activity(session['user_id'], 'logout', 'User logged out')
        print(f"👤 User {session.get('username')} logged out from IP: {request.remote_addr}")
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

@app.route('/report-lost', methods=['GET', 'POST'])
@csrf_protected
def report_lost():
    if request.method == 'POST':
        category = sanitize_input(request.form['category'])
        description = sanitize_input(request.form['description'])
        color = sanitize_input(request.form.get('color', ''))
        brand = sanitize_input(request.form.get('brand', ''))
        location = sanitize_input(request.form['location'])
        contact_phone = sanitize_input(request.form.get('contact_phone', ''))
        verification_question1 = sanitize_input(request.form.get('verification_question1', ''))
        verification_answer1 = sanitize_input(request.form.get('verification_answer1', ''))
        verification_question2 = sanitize_input(request.form.get('verification_question2', ''))
        verification_answer2 = sanitize_input(request.form.get('verification_answer2', ''))
        serial_number = sanitize_input(request.form.get('serial_number', ''))
        
        errors = validate_item_data(category, description, location)
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('report_lost.html')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO items (type, category, description, color, brand, location_found_lost, 
                              date_reported, phone, verification_question1, verification_answer1,
                              verification_question2, verification_answer2, serial_number)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, ('lost', category, description, color, brand, location, date.today(), 
              contact_phone, verification_question1, verification_answer1,
              verification_question2, verification_answer2, serial_number))
        
        conn.commit()
        item_id = cursor.lastrowid
        
        claim_id = generate_unique_claim_id('LOST', item_id)
        try:
            cursor.execute("UPDATE items SET claim_id = %s WHERE id = %s", (claim_id, item_id))
            conn.commit()
        except Exception as e:
            print(f"Note: claim_id column not available yet: {e}")
        
        cursor.close()
        conn.close()
        
        # Match search with debug output
        print(f"🔍 Searching matches for new lost item ID: {item_id}")
        matches = find_matches(item_id)
        
        if matches > 0:
            flash(f'✅ Lost item reported to SKS Mall! Claim ID: {claim_id}. Found {matches} potential match(es).', 'success')
        else:
            flash(f'✅ Lost item reported to SKS Mall successfully. Claim ID: {claim_id}', 'info')
        
        return redirect(url_for('index'))
    
    return render_template('report_lost.html')

@app.route('/report-found', methods=['GET', 'POST'])
@csrf_protected
def report_found():
    if request.method == 'POST':
        category = sanitize_input(request.form['category'])
        description = sanitize_input(request.form['description'])
        color = sanitize_input(request.form.get('color', ''))
        brand = sanitize_input(request.form.get('brand', ''))
        location = sanitize_input(request.form['location'])
        storage_loc = sanitize_input(request.form.get('storage_location', ''))
        reporter_name = sanitize_input(request.form.get('reporter_name', ''))
        reporter_contact = sanitize_input(request.form.get('reporter_contact', ''))
        
        errors = validate_item_data(category, description, location)
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('report_found.html')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO items (type, category, description, color, brand, location_found_lost, date_reported, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'open')
        """, ('found', category, description, color, brand, location, date.today()))
        
        conn.commit()
        item_id = cursor.lastrowid
        
        claim_id = generate_unique_claim_id('FOUND', item_id)
        try:
            cursor.execute("UPDATE items SET claim_id = %s WHERE id = %s", (claim_id, item_id))
            conn.commit()
        except Exception as e:
            print(f"Note: claim_id column not available yet: {e}")
        
        if storage_loc:
            try:
                cursor.execute("""
                    INSERT INTO storage (item_id, shelf_location, stored_date)
                    VALUES (%s, %s, %s)
                """, (item_id, storage_loc, date.today()))
                conn.commit()
            except:
                pass
        
        cursor.close()
        conn.close()
        
        qr_code = generate_claim_qr(claim_id, item_id)
        
        return render_template('report_found.html', 
                             submitted=True,
                             claim_id=claim_id,
                             qr_code=qr_code)
    
    return render_template('report_found.html')

@app.route('/search')
def search():
    query = sanitize_input(request.args.get('q', ''))
    conn = get_db_connection()
    cursor = conn.cursor()  # FIXED: removed dictionary=True
    if query:
        cursor.execute("""
            SELECT * FROM items 
            WHERE (description LIKE %s OR category LIKE %s OR brand LIKE %s)
            AND status != 'archived'
            ORDER BY date_reported DESC
        """, (f'%{query}%', f'%{query}%', f'%{query}%'))
    else:
        cursor.execute("""
            SELECT * FROM items 
            WHERE status != 'archived'
            ORDER BY date_reported DESC 
            LIMIT 50
        """)
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('search.html', items=items, query=query)

# ========== CLAIM ITEM ==========
@app.route('/claim-item', methods=['GET', 'POST'])
@csrf_protected
def claim_item():
    if request.method == 'POST':
        claimant_name = sanitize_input(request.form.get('claimant_name', ''))
        claimant_email = sanitize_input(request.form.get('claimant_email', ''))
        claimant_phone = sanitize_input(request.form.get('claimant_phone', ''))
        item_id = request.form.get('item_id')
        verification_details = sanitize_input(request.form.get('verification_details', ''))
        
        print(f"📝 Claim submission: {claimant_name}, {claimant_email}, item: {item_id}")
        
        if not claimant_name or not claimant_email or not item_id:
            flash('Please fill in all required fields', 'danger')
            return render_template('claim_item.html')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO claims (item_id, claimant_name, claimant_contact, 
                                  status, verification_notes, claim_date)
                VALUES (%s, %s, %s, 'pending', %s, CURDATE())
            """, (item_id, claimant_name, claimant_email, verification_details))
            conn.commit()
            claim_db_id = cursor.lastrowid
            
            claim_id = generate_unique_claim_id('CLM', claim_db_id)
            try:
                cursor.execute("UPDATE claims SET claim_id = %s WHERE id = %s", (claim_id, claim_db_id))
                conn.commit()
            except Exception as e:
                print(f"Note: claim_id column not available yet: {e}")
                claim_id = f"CLM-{datetime.now().strftime('%Y%m%d')}-{str(claim_db_id).zfill(4)}"
            
            cursor.execute("SELECT category, description FROM items WHERE id = %s", (item_id,))
            item = cursor.fetchone()
            
            qr_code = generate_claim_qr(claim_id)
            
            session['last_claim'] = {
                'claim_id': claim_id,
                'claimant_name': claimant_name,
                'claimant_email': claimant_email,
                'claimant_phone': claimant_phone,
                'item_category': item[0] if item else 'Unknown',
                'item_description': item[1] if item else '',
                'qr_code': qr_code,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            
            send_claim_confirmation_email(claimant_email, claimant_name, claim_id, 
                                         {'category': item[0] if item else 'Item', 
                                          'description': item[1] if item else ''})
            
            flash(f'✅ Claim submitted to SKS Mall successfully! Your Claim ID: {claim_id}', 'success')
            return redirect(url_for('claim_success'))
            
        except Exception as e:
            conn.rollback()
            flash(f'Error submitting claim: {str(e)}', 'danger')
            print(f"❌ Claim submission error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            cursor.close()
            conn.close()
        
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor()  # FIXED: removed dictionary=True
    
    pre_selected_item_id = request.args.get('item_id')
    
    cursor.execute("""
        SELECT id, category, description, date_reported, location_found_lost 
        FROM items 
        WHERE type = 'lost' AND status = 'open'
        ORDER BY date_reported DESC
    """)
    lost_items = cursor.fetchall()
    
    pre_selected_item = None
    if pre_selected_item_id:
        for item in lost_items:
            if str(item['id']) == str(pre_selected_item_id):
                pre_selected_item = item
                break
    
    cursor.close()
    conn.close()
    
    return render_template('claim_item.html', 
                         lost_items=lost_items,
                         pre_selected_item=pre_selected_item)

@app.route('/claim-success')
def claim_success():
    claim_data = session.get('last_claim')
    if not claim_data:
        flash('No claim data found. Please submit a claim first.', 'warning')
        return redirect(url_for('claim_item'))
    return render_template('claim_success.html', claim=claim_data)

# ========== TRACK CLAIM ==========
@app.route('/track-claim', methods=['GET', 'POST'])
@csrf_protected
def track_claim():
    claim_id_param = request.args.get('claim_id')
    if claim_id_param:
        conn = get_db_connection()
        cursor = conn.cursor()  # FIXED: removed dictionary=True
        claim = None
        
        try:
            if claim_id_param.startswith('LOST') or claim_id_param.startswith('FOUND'):
                cursor.execute("""
                    SELECT *, 'item' as source
                    FROM items 
                    WHERE claim_id = %s
                """, (claim_id_param,))
                item = cursor.fetchone()
                
                if item:
                    if item['status'] == 'ready_for_collection':
                        status_display = 'Ready for Collection ✅'
                    elif item['status'] == 'claimed':
                        status_display = 'Claimed ✅'
                    elif item['status'] == 'open':
                        status_display = 'Pending Review ⏳'
                    else:
                        status_display = item['status']
                    
                    claim = {
                        'claim_id': item['claim_id'],
                        'claimant_name': 'Not specified',
                        'claimant_contact': 'Not specified',
                        'claimant_phone': item.get('phone', 'Not specified'),
                        'category': item['category'],
                        'description': item['description'],
                        'location_found_lost': item.get('location_found_lost', 'Not specified'),
                        'status': status_display,
                        'created_at': item.get('date_reported'),
                        'claim_date': item.get('claim_date'),
                        'verification_notes': f'Item reported as {item["type"]}',
                        'is_item': True
                    }
            
            elif claim_id_param.startswith('CLM'):
                cursor.execute("""
                    SELECT c.*, i.category, i.description, i.location_found_lost
                    FROM claims c
                    JOIN items i ON c.item_id = i.id
                    WHERE c.claim_id = %s
                """, (claim_id_param,))
                claim_data = cursor.fetchone()
                
                if claim_data:
                    status_map = {
                        'pending': 'Pending Review ⏳',
                        'approved': 'Ready for Collection ✅',
                        'rejected': 'Rejected ❌'
                    }
                    claim = claim_data
                    claim['status'] = status_map.get(claim_data['status'], claim_data['status'])
                    claim['is_item'] = False
            
        except Exception as e:
            print(f"Track claim error: {e}")
            claim = None
        
        cursor.close()
        conn.close()
        
        if claim:
            return render_template('track_claim_result.html', claim=claim)
        else:
            flash('Claim ID not found at SKS Mall. Please check and try again.', 'danger')
    
    if request.method == 'POST':
        claim_id = sanitize_input(request.form['claim_id'])
        
        conn = get_db_connection()
        cursor = conn.cursor()  # FIXED: removed dictionary=True
        claim = None
        
        try:
            if claim_id.startswith('LOST') or claim_id.startswith('FOUND'):
                cursor.execute("""
                    SELECT *, 'item' as source
                    FROM items 
                    WHERE claim_id = %s
                """, (claim_id,))
                item = cursor.fetchone()
                
                if item:
                    if item['status'] == 'ready_for_collection':
                        status_display = 'Ready for Collection ✅'
                    elif item['status'] == 'claimed':
                        status_display = 'Claimed ✅'
                    elif item['status'] == 'open':
                        status_display = 'Pending Review ⏳'
                    else:
                        status_display = item['status']
                    
                    claim = {
                        'claim_id': item['claim_id'],
                        'claimant_name': 'Not specified',
                        'claimant_contact': 'Not specified',
                        'claimant_phone': item.get('phone', 'Not specified'),
                        'category': item['category'],
                        'description': item['description'],
                        'location_found_lost': item.get('location_found_lost', 'Not specified'),
                        'status': status_display,
                        'created_at': item.get('date_reported'),
                        'claim_date': item.get('claim_date'),
                        'verification_notes': f'Item reported as {item["type"]}',
                        'is_item': True
                    }
            
            elif claim_id.startswith('CLM'):
                cursor.execute("""
                    SELECT c.*, i.category, i.description, i.location_found_lost
                    FROM claims c
                    JOIN items i ON c.item_id = i.id
                    WHERE c.claim_id = %s
                """, (claim_id,))
                claim_data = cursor.fetchone()
                
                if claim_data:
                    status_map = {
                        'pending': 'Pending Review ⏳',
                        'approved': 'Ready for Collection ✅',
                        'rejected': 'Rejected ❌'
                    }
                    claim = claim_data
                    claim['status'] = status_map.get(claim_data['status'], claim_data['status'])
                    claim['is_item'] = False
            
        except Exception as e:
            print(f"Track claim error: {e}")
            claim = None
        
        cursor.close()
        conn.close()
        
        if claim:
            return render_template('track_claim_result.html', claim=claim)
        else:
            flash('Claim ID not found at SKS Mall. Please check and try again.', 'danger')
    
    return render_template('track_claim.html')

# ========== FIXED STAFF DASHBOARD ==========
@app.route('/staff/dashboard')
@staff_required
def staff_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()  # FIXED: removed dictionary=True
    
    # Pending Items
    cursor.execute("""
        SELECT *, claim_id
        FROM items 
        WHERE status = 'open' OR status = 'pending'
        ORDER BY date_reported DESC
    """)
    pending_items = cursor.fetchall()
    
    # Pending Matches
    cursor.execute("""
        SELECT m.*, 
               l.category as lost_category, 
               l.phone as lost_phone, 
               l.claim_id as lost_claim_id,
               l.description as lost_description,
               l.color as lost_color,
               l.brand as lost_brand,
               f.category as found_category, 
               f.phone as found_phone, 
               f.claim_id as found_claim_id,
               f.description as found_description,
               f.color as found_color,
               f.brand as found_brand
        FROM matches m
        JOIN items l ON m.lost_item_id = l.id
        JOIN items f ON m.found_item_id = f.id
        WHERE m.status = 'pending'
        ORDER BY m.match_score DESC
    """)
    pending_matches = cursor.fetchall()
    
    print(f"🔍 Staff Dashboard - Found {len(pending_matches)} pending matches")
    if pending_matches:
        for match in pending_matches:
            print(f"   Match ID: {match['id']}, Score: {match['match_score']}, Lost: {match['lost_category']}, Found: {match['found_category']}")
    
    # Pending Claims
    try:
        cursor.execute("""
            SELECT c.*, i.category, i.description, i.location_found_lost,
                   i.verification_question1, i.verification_answer1,
                   i.verification_question2, i.verification_answer2, 
                   i.claim_id as item_claim_id
            FROM claims c
            JOIN items i ON c.item_id = i.id
            WHERE c.status = 'pending'
            ORDER BY c.created_at DESC
        """)
        pending_claims = cursor.fetchall()
    except:
        pending_claims = []
    
    # Ready for Collection - Shows BOTH sources
    cursor.execute("""
        SELECT 
            'item' as source,
            i.id,
            i.claim_id,
            i.category,
            i.description,
            i.location_found_lost,
            i.status as item_status,
            'Not specified' as claimant_name,
            'Not specified' as claimant_contact,
            'Ready for Collection' as display_status,
            i.date_reported as created_at
        FROM items i
        WHERE i.status = 'ready_for_collection'
        
        UNION
        
        SELECT 
            'claim' as source,
            c.id,
            c.claim_id,
            i.category,
            i.description,
            i.location_found_lost,
            i.status as item_status,
            c.claimant_name,
            c.claimant_contact,
            'Ready for Collection' as display_status,
            c.created_at
        FROM claims c
        JOIN items i ON c.item_id = i.id
        WHERE c.status = 'approved'
        
        ORDER BY created_at DESC
    """)
    ready_collection = cursor.fetchall()
    
    # Debug output
    print(f"🔍 Ready for Collection: {len(ready_collection)} items")
    for item in ready_collection:
        print(f"   {item['claim_id']} - {item['category']} - Source: {item['source']}")
    
    total_pending_items = len(pending_items)
    total_pending_matches = len(pending_matches)
    total_claims_verify = len(pending_claims)
    total_ready_collection = len(ready_collection)
    
    cursor.close()
    conn.close()
    
    return render_template('staff_dashboard.html', 
                         pending_items=pending_items,
                         pending_matches=pending_matches,
                         pending_claims=pending_claims,
                         ready_collection=ready_collection,
                         total_pending_items=total_pending_items,
                         total_pending_matches=total_pending_matches,
                         total_claims_verify=total_claims_verify,
                         total_ready_collection=total_ready_collection)

# ========== STAFF VERIFY CLAIM ==========
@app.route('/staff/verify-claim/<int:claim_id>', methods=['POST'])
@staff_required
@csrf_protected
def verify_claim(claim_id):
    claimant_answers = sanitize_input(request.form.get('claimant_answers', ''))
    id_verified = 1 if request.form.get('id_verified') == '1' else 0
    id_card_number = sanitize_input(request.form.get('id_card_number', ''))
    answers_match = sanitize_input(request.form.get('answers_match', ''))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if answers_match == 'yes':
            cursor.execute("""
                UPDATE claims 
                SET status = 'approved', 
                    id_verified = %s, 
                    id_card_number = %s, 
                    verification_answers = %s, 
                    answers_match = %s
                WHERE id = %s
            """, (id_verified, id_card_number, claimant_answers, answers_match, claim_id))
            
            cursor.execute("SELECT item_id FROM claims WHERE id = %s", (claim_id,))
            claim_data = cursor.fetchone()
            
            if claim_data:
                cursor.execute("""
                    UPDATE items 
                    SET status = 'claimed', claim_date = CURDATE()
                    WHERE id = %s
                """, (claim_data[0],))
                
                cursor.execute("SELECT claimant_contact FROM claims WHERE id = %s", (claim_id,))
                claimant = cursor.fetchone()
                if claimant and claimant[0]:
                    send_claim_status_email(claimant[0], "Valued Customer", f"CLM-{claim_id}", 'approved', "")
            
            flash('✅ Claim verified and approved!', 'success')
            
        elif answers_match == 'partial':
            flash('⚠️ Partial match - Need more evidence', 'warning')
            
        else:
            cursor.execute("""
                UPDATE claims 
                SET status = 'rejected', 
                    verification_answers = %s, 
                    answers_match = %s
                WHERE id = %s
            """, (claimant_answers, answers_match, claim_id))
            flash('❌ Claim rejected.', 'danger')
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        flash(f'Error: {str(e)}', 'danger')
        print(f"❌ Verification error: {e}")
    
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('staff_dashboard'))

# ========== STAFF CONFIRM MATCH ==========
@app.route('/staff/confirm-match/<int:match_id>')
@staff_required
def confirm_match(match_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Update match status
    cursor.execute("UPDATE matches SET status = 'confirmed' WHERE id = %s", (match_id,))
    conn.commit()
    
    # Get the lost item to update status
    cursor.execute("""
        SELECT lost_item_id FROM matches WHERE id = %s
    """, (match_id,))
    match_data = cursor.fetchone()
    
    if match_data:
        cursor.execute("""
            UPDATE items 
            SET status = 'ready_for_collection' 
            WHERE id = %s
        """, (match_data[0],))
        conn.commit()
        print(f"✅ Item {match_data[0]} marked as ready for collection")
    
    cursor.close()
    conn.close()
    
    flash('✅ Match confirmed! Item is ready for collection.', 'success')
    return redirect(url_for('staff_dashboard'))

@app.route('/staff/items')
@staff_required
def manage_items():
    conn = get_db_connection()
    cursor = conn.cursor()  # FIXED: removed dictionary=True
    cursor.execute("SELECT * FROM items ORDER BY date_reported DESC")
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('staff_items.html', items=items)

# ========== VIEW CLAIM ==========
@app.route('/staff/view-claim/<int:claim_id>')
@staff_required
def view_claim(claim_id):
    print(f"🔍 VIEW CLAIM CALLED: ID = {claim_id}")
    
    conn = get_db_connection()
    cursor = conn.cursor()  # FIXED: removed dictionary=True
    
    try:
        cursor.execute("""
            SELECT c.*, i.category, i.description, i.location_found_lost,
                   i.verification_question1, i.verification_answer1,
                   i.verification_question2, i.verification_answer2
            FROM claims c
            JOIN items i ON c.item_id = i.id
            WHERE c.id = %s
        """, (claim_id,))
        claim = cursor.fetchone()
        print(f"📋 Claim found: {claim is not None}")
    except Exception as e:
        print(f"Error viewing claim: {e}")
        claim = None
    finally:
        cursor.close()
        conn.close()
    
    if not claim:
        flash('Claim not found', 'danger')
        return redirect(url_for('staff_dashboard'))
    
    return render_template('view_item.html', claim=claim)

# ========== DEBUG TEST ROUTE ==========
@app.route('/staff/test-view')
@staff_required
def test_view():
    return """
    <div style='text-align:center; padding:50px; font-family:Arial;'>
        <h1 style='color:green;'>✅ TEST ROUTE WORKS!</h1>
        <a href='/staff/dashboard'>Back to Dashboard</a>
    </div>
    """

# ========== SECURITY DASHBOARD ==========
@app.route('/admin/security')
@admin_required
def security_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()  # FIXED: removed dictionary=True
    
    try:
        cursor.execute("SELECT COUNT(*) as failed FROM activity_log WHERE action = 'failed_login'")
        failed = cursor.fetchone()
    except:
        failed = {'failed': 0}
    
    try:
        cursor.execute("""
            SELECT l.*, u.username 
            FROM activity_log l 
            LEFT JOIN users u ON l.user_id = u.id 
            ORDER BY l.created_at DESC 
            LIMIT 20
        """)
        recent_logs = cursor.fetchall()
    except:
        recent_logs = []
    
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE is_active = TRUE")
    active_users = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return render_template('security.html', 
                         failed=failed, 
                         recent_logs=recent_logs,
                         active_users=active_users)

# ========== Admin Routes ==========
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()  # FIXED: removed dictionary=True
    cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
    users = cursor.fetchall()
    cursor.execute("SELECT * FROM items ORDER BY date_reported DESC")
    items = cursor.fetchall()
    try:
        cursor.execute("SELECT c.*, i.category FROM claims c LEFT JOIN items i ON c.item_id = i.id ORDER BY c.created_at DESC")
        claims = cursor.fetchall()
    except:
        claims = []
    try:
        cursor.execute("SELECT l.*, u.username FROM activity_log l LEFT JOIN users u ON l.user_id = u.id ORDER BY l.created_at DESC LIMIT 50")
        logs = cursor.fetchall()
    except:
        logs = []
    cursor.execute("SELECT COUNT(*) as total_items, SUM(CASE WHEN type='lost' THEN 1 ELSE 0 END) as lost_items, SUM(CASE WHEN type='found' THEN 1 ELSE 0 END) as found_items, SUM(CASE WHEN status='claimed' THEN 1 ELSE 0 END) as claimed_items FROM items")
    stats = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('admin.html', users=users, items=items, claims=claims, logs=logs, stats=stats)

@app.route('/admin/create-user', methods=['POST'])
@admin_required
@csrf_protected
def create_user():
    username = sanitize_input(request.form['username'])
    password = request.form['password']
    role = sanitize_input(request.form['role'])
    full_name = sanitize_input(request.form['full_name'])
    email = sanitize_input(request.form.get('email', ''))
    
    if not email:
        flash('Email is required for security notifications', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    is_strong, msg = is_strong_password(password)
    if not is_strong:
        flash(msg, 'danger')
        return redirect(url_for('admin_dashboard'))
    
    hashed_pw = hash_password(password)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, full_name, email, is_active, failed_login_attempts, lockout_time)
            VALUES (%s, %s, %s, %s, %s, TRUE, 0, NULL)
        """, (username, hashed_pw, role, full_name, email))
        conn.commit()
        flash(f'✅ User {username} created successfully! Login alerts will be sent to {email}', 'success')
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'danger')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-user/<int:user_id>')
@admin_required
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s AND role != 'admin'", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('User deleted', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-item/<int:item_id>')
@admin_required
def delete_item(item_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM storage WHERE item_id = %s", (item_id,))
    cursor.execute("DELETE FROM claims WHERE item_id = %s", (item_id,))
    cursor.execute("DELETE FROM matches WHERE lost_item_id = %s OR found_item_id = %s", (item_id, item_id))
    cursor.execute("DELETE FROM items WHERE id = %s", (item_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Item deleted from SKS Mall system', 'success')
    return redirect(url_for('admin_dashboard'))

# ========== QR Posters Route ==========
@app.route('/staff/qr-posters')
@staff_required
def qr_posters():
    base_url = BASE_URL
    lost_qr = generate_claim_qr_for_page(f"{base_url}/report-lost")
    found_qr = generate_claim_qr_for_page(f"{base_url}/report-found")
    claim_qr = generate_claim_qr_for_page(f"{base_url}/claim-item")
    track_qr = generate_claim_qr_for_page(f"{base_url}/track-claim")
    return render_template('qr_posters.html', 
                         lost_qr=lost_qr,
                         found_qr=found_qr,
                         claim_qr=claim_qr,
                         track_qr=track_qr)

@app.route('/staff/qr-codes')
@staff_required
def qr_codes():
    base_url = BASE_URL
    lost_qr = generate_claim_qr_for_page(f"{base_url}/report-lost")
    found_qr = generate_claim_qr_for_page(f"{base_url}/report-found")
    claim_qr = generate_claim_qr_for_page(f"{base_url}/claim-item")
    track_qr = generate_claim_qr_for_page(f"{base_url}/track-claim")
    return render_template('qr_print.html', 
                         lost_qr=lost_qr,
                         found_qr=found_qr,
                         claim_qr=claim_qr,
                         track_qr=track_qr,
                         base_url=base_url)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
