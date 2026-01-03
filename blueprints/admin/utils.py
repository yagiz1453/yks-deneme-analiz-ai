from flask import request
import os
import sqlite3

import sqlite3
def get_db():
    db_path = os.path.join(os.getcwd(), 'veritabani.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # <--- bu satır çok önemli
    return conn

def get_client_ip():
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0].split(',')[0]
    elif request.headers.get("X-Real-IP"):
        ip = request.headers.get("X-Real-IP")
    else:
        ip = request.remote_addr or "unknown"
    if ip in ("127.0.0.1", "::1"):
        ip = "local-development"
    return ip

def add_admin_auth_log(username, ip, status, detail=""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO admin_auth_logs (username, ip_address, status, detail) VALUES (?, ?, ?, ?)",
        (username, ip, status, detail)
    )
    conn.commit()
    conn.close()
