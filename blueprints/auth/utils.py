import re
import os
import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from itsdangerous import URLSafeTimedSerializer
from flask import current_app, render_template, url_for, request
from datetime import datetime
import uuid
from werkzeug.security import generate_password_hash

def get_db():
    db_path = os.path.join(os.getcwd(), 'veritabani.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# === 🛠 TABLO OLUŞTURMA ===

def init_user_table():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            uuid TEXT UNIQUE NOT NULL,
            registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            news_permission INTEGER DEFAULT 1,
            mandatory_email_permission INTEGER DEFAULT 1,
            is_verified INTEGER DEFAULT 0,
            verify_token TEXT,
            last_verification_sent DATETIME
        )
    ''')
    conn.commit()
    conn.close()

def init_auth_log_table():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            ip_address TEXT,
            action TEXT,
            status TEXT,
            detail TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def init_admin_auth_log_table():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_auth_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            ip_address TEXT,
            status TEXT,
            detail TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# Uygulama başlangıcında tablo kontrolleri
init_user_table()
init_auth_log_table()
init_admin_auth_log_table()

def check_and_update_user_table_schema():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cursor.fetchone() is None:
        init_user_table()
        conn.close()
        return

    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]

    column_defs = {
        'registration_date': "DATETIME DEFAULT CURRENT_TIMESTAMP",
        'ip_address': "TEXT",
        'news_permission': "INTEGER DEFAULT 1",
        'mandatory_email_permission': "INTEGER DEFAULT 1",
        'is_verified': "INTEGER DEFAULT 0",
        'verify_token': "TEXT",
        'last_verification_sent': "DATETIME"
    }

    for column, definition in column_defs.items():
        if column not in columns:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
                conn.commit()
                print(f"'{column}' sütunu eklendi.")
            except sqlite3.Error as e:
                print(f"Hata: {e}")
    conn.close()

# === 🔐 KULLANICI KAYIT / DOĞRULAMA ===

def is_valid_email(email):
    allowed_domains = [
        r'@gmail\.com$', r'@hotmail\.com$', r'@hotmail\.co\.uk$', r'@hotmail\.com\.tr$',
        r'@outlook\.com$', r'@outlook\.com\.tr$', r'@yahoo\.com$',
        r'@icloud\.com$', r'@protonmail\.com$', r'@tutanota\.com$'
    ]
    return any(re.search(pattern, email) for pattern in allowed_domains)

def is_medium_strong_password(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Şifre en az 8 karakter uzunluğunda olmalıdır."
    if not re.search(r"[A-Z]", password):
        return False, "Şifre en az bir büyük harf içermelidir."
    if not re.search(r"[a-z]", password):
        return False, "Şifre en az bir küçük harf içermelidir."
    if not re.search(r"\d", password):
        return False, "Şifre en az bir rakam içermelidir."
    return True, "Şifre güçlü."

def get_serializer():
    return URLSafeTimedSerializer(current_app.secret_key)

def create_user(name, email, password, ip_address, news_permission, mandatory_email_permission, verify_token):
    password_hash = generate_password_hash(password)
    user_uuid = str(uuid.uuid4())
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (name, email, password_hash, uuid, ip_address, news_permission, mandatory_email_permission, is_verified, verify_token) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)",
                   (name, email, password_hash, user_uuid, ip_address, news_permission, mandatory_email_permission, verify_token))
    conn.commit()
    conn.close()
    return user_uuid

def update_verification_token_and_time(user_id):
    token = str(uuid.uuid4())
    now = datetime.utcnow()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET verify_token = ?, last_verification_sent = ? WHERE id = ?", (token, now, user_id))
    conn.commit()
    conn.close()
    return token

def update_verification_sent_time(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_verification_sent = ? WHERE id = ?", (datetime.utcnow(), user_id))
    conn.commit()
    conn.close()

def set_user_verified(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_verified = 1, verify_token = NULL WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

# === 📩 E-POSTA ===

def send_verification_email(to_email, user_name, verify_token):
    sender_email = os.environ.get("GMAIL_USER")
    sender_password = os.environ.get("GMAIL_APP_PASSWORD")
    subject = "Hesabınızı Doğrulayın - YKS Deneme Analiz"
    verify_link = url_for('auth.verify_email', token=verify_token, _external=True)
    body = render_template('email/verification.html', user_name=user_name, verify_link=verify_link)
    return _send_email(sender_email, sender_password, to_email, subject, body)

def send_welcome_email(to_email, user_name):
    sender_email = os.environ.get("GMAIL_USER")
    sender_password = os.environ.get("GMAIL_APP_PASSWORD")
    subject = "Hoş Geldiniz - YKS Deneme Analiz"
    body = render_template('email/welcome.html', user_name=user_name)
    return _send_email(sender_email, sender_password, to_email, subject, body)

def send_reset_password_email(to_email, user_name, token):
    sender_email = os.environ.get("GMAIL_USER")
    sender_password = os.environ.get("GMAIL_APP_PASSWORD")
    subject = "Şifre Sıfırlama - YKS Deneme Analiz"
    reset_link = reset_link = f"{request.url_root}reset-password/{token}"
    body = render_template('email/reset_password.html', user_name=user_name, reset_link=reset_link)
    return _send_email(sender_email, sender_password, to_email, subject, body)

def _send_email(sender, password, to, subject, body):
    if not sender or not password:
        print("SMTP kimlik bilgileri eksik.")
        return False
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, to, msg.as_string())
        return True
    except Exception as e:
        print(f"E-posta gönderilemedi: {e}")
        return False

# === 🔍 SORGULAR ===

def get_user_by_email(email):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_verify_token(token):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE verify_token = ?", (token,))
    user = cursor.fetchone()
    conn.close()
    return user

# === 🌐 IP ve LOG ===

def get_client_ip():
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR']
    return request.remote_addr

def add_auth_log(email, ip, action, status, detail=""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO auth_logs (email, ip_address, action, status, detail)
        VALUES (?, ?, ?, ?, ?)
    """, (email, ip, action, status, detail))
    conn.commit()
    conn.close()

def add_admin_auth_log(username, ip, status, detail=""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO admin_auth_logs (username, ip_address, status, detail)
        VALUES (?, ?, ?, ?)
    """, (username, ip, status, detail))
    conn.commit()
    conn.close()
