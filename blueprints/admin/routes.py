import os
import re
import bcrypt
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import (
    render_template, render_template_string, request, redirect,
    url_for, flash, session
)
from werkzeug.utils import secure_filename
from . import admin_bp
from .utils import get_client_ip, add_admin_auth_log, get_db

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")  # Hash bekleniyor

EMAIL_TEMPLATES_DIR = os.path.join(os.getcwd(), "templates", "email")

def is_admin_logged_in():
    return session.get("is_admin") == True

@admin_bp.context_processor
def inject_csrf_token():
    from flask_wtf.csrf import generate_csrf
    return dict(csrf_token=generate_csrf)

@admin_bp.route('/supersecretadmin', methods=['GET', 'POST'])
def admin_login():
    if is_admin_logged_in():
        return redirect(url_for('admin.admin_panel'))

    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        ip_address = get_client_ip()

        # Ortam değişkenlerinin yüklenip yüklenmediğini kontrol et
        if not ADMIN_USERNAME or not ADMIN_PASSWORD:
            flash("Sunucu yapılandırma hatası: Admin bilgileri eksik.", "danger")
            # Geliştirme ortamı için loglama
            print("HATA: ADMIN_USERNAME veya ADMIN_PASSWORD ortam değişkenleri ayarlanmamış.")
            return render_template('admin/admin-login.html')

        # Şifre hash'ini ortam değişkeninden al
        hashed_password = ADMIN_PASSWORD.encode('utf-8')

        if username == ADMIN_USERNAME and bcrypt.checkpw(password.encode('utf-8'), hashed_password):
            session['is_admin'] = True
            flash("Admin olarak giriş yaptınız.", "success")
            add_admin_auth_log(username, ip_address, "success", "Admin giriş başarılı")
            return redirect(url_for('admin.admin_panel'))
        else:
            flash("Kullanıcı adı veya şifre hatalı.", "danger")
            add_admin_auth_log(username, ip_address, "fail", "Admin giriş başarısız")
    return render_template('admin/admin-login.html')

@admin_bp.route('/supersecretadmin/panel')
def admin_panel():
    if not is_admin_logged_in():
        return redirect(url_for('admin.admin_login'))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE news_permission = 1")
    news_perm_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE mandatory_email_permission = 1")
    mandatory_perm_count = cursor.fetchone()[0]
    conn.close()
    return render_template(
        'admin/admin-panel.html',
        users=users,
        total_users=total_users,
        news_perm_count=news_perm_count,
        mandatory_perm_count=mandatory_perm_count
    )

@admin_bp.route('/supersecretadmin/logout')
def admin_logout():
    session.pop('is_admin', None)
    flash("Admin oturumu kapatıldı.", "success")
    return redirect(url_for('admin.admin_login'))

@admin_bp.route('/supersecretadmin/email-templates')
def admin_email_templates():
    if not is_admin_logged_in():
        return redirect(url_for('admin.admin_login'))
    templates = [
        f for f in os.listdir(EMAIL_TEMPLATES_DIR)
        if os.path.isfile(os.path.join(EMAIL_TEMPLATES_DIR, f)) and f.endswith(".html")
    ]
    return render_template('admin/admin-email-templates.html', templates=templates)

@admin_bp.route('/supersecretadmin/email-templates/upload', methods=['POST'])
def admin_email_template_upload():
    if not is_admin_logged_in():
        return redirect(url_for('admin.admin_login'))
    file = request.files.get('file')
    if not file or file.filename == '':
        flash("Dosya seçilmedi.", "danger")
        return redirect(url_for('admin.admin_email_templates'))
    filename = secure_filename(file.filename)
    if not filename.endswith('.html'):
        flash("Sadece .html dosyası yükleyebilirsiniz.", "danger")
        return redirect(url_for('admin.admin_email_templates'))
    save_path = os.path.join(EMAIL_TEMPLATES_DIR, filename)
    file.save(save_path)
    flash(f"{filename} başarıyla yüklendi.", "success")
    return redirect(url_for('admin.admin_email_templates'))

@admin_bp.route('/supersecretadmin/email-templates/delete/<filename>', methods=['POST'])
def admin_email_template_delete(filename):
    if not is_admin_logged_in():
        return redirect(url_for('admin.admin_login'))
    safe_name = secure_filename(filename)
    file_path = os.path.join(EMAIL_TEMPLATES_DIR, safe_name)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash(f"{safe_name} silindi.", "success")
    else:
        flash("Dosya bulunamadı.", "danger")
    return redirect(url_for('admin.admin_email_templates'))

@admin_bp.route('/supersecretadmin/email-templates/view/<filename>')
def admin_email_template_view(filename):
    if not is_admin_logged_in():
        return redirect(url_for('admin.admin_login'))
    safe_name = secure_filename(filename)
    file_path = os.path.join(EMAIL_TEMPLATES_DIR, safe_name)
    if not os.path.exists(file_path):
        flash("Dosya bulunamadı.", "danger")
        return redirect(url_for('admin.admin_email_templates'))
    with open(file_path, encoding="utf-8") as f:
        content = f.read()
    return render_template('admin/admin-email-template-view.html', filename=safe_name, content=content)

# --- YENİ EKLENENLER ---

def send_gmail_smtp(to_email, subject, body):
    sender_email = os.environ.get("GMAIL_USER")
    sender_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not sender_email or not sender_password:
        print("GMAIL_USER veya GMAIL_APP_PASSWORD .env'de tanımlı değil.")
        return False

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"SMTP gönderim hatası: {e}")
        return False

def extract_template_variables(template_text):
    # Basitçe {{ variable }} kalıplarını buluyor
    return re.findall(r"{{\s*(\w+)\s*}}", template_text)

def list_email_templates():
    return [
        f for f in os.listdir(EMAIL_TEMPLATES_DIR)
        if os.path.isfile(os.path.join(EMAIL_TEMPLATES_DIR, f)) and f.endswith(".html")
    ]

@admin_bp.route('/supersecretadmin/send-email/mandatory', methods=['GET', 'POST'])
def admin_send_email_mandatory():
    if not is_admin_logged_in():
        return redirect(url_for('admin.admin_login'))

    templates = list_email_templates()
    selected_template = request.args.get('template_name', '') or None
    subject = ""
    variables = []
    variable_map = {}

    if selected_template:
        template_path = os.path.join(EMAIL_TEMPLATES_DIR, secure_filename(selected_template))
        if os.path.exists(template_path):
            with open(template_path, encoding="utf-8") as f:
                template_content = f.read()
            variables = extract_template_variables(template_content)

    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        template_name = request.form.get('template_name', '').strip()
        variable_map = {}
        for key in request.form:
            if key.startswith('varmap_'):
                var = key.replace('varmap_', '')
                variable_map[var] = request.form[key]

        if not subject or not template_name:
            flash("Konu ve şablon seçimi zorunludur.", "danger")
            return redirect(url_for('admin.admin_send_email_mandatory'))

        template_path = os.path.join(EMAIL_TEMPLATES_DIR, secure_filename(template_name))
        if not os.path.exists(template_path):
            flash("Seçilen şablon bulunamadı.", "danger")
            return redirect(url_for('admin.admin_send_email_mandatory'))

        with open(template_path, encoding="utf-8") as f:
            template_content = f.read()

        variables = extract_template_variables(template_content)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, uuid FROM users WHERE mandatory_email_permission = 1")
        users = cursor.fetchall()
        conn.close()

        sent_count = 0
        for user in users:
            context = {}
            for var in variables:
                field = variable_map.get(var, var)
                context[var] = user[field] if field in user.keys() else ""
            body = render_template_string(template_content, **context)
            if send_gmail_smtp(user["email"], subject, body):
                sent_count += 1

        flash(f"Zorunlu izin veren {len(users)} kullanıcıdan {sent_count} kişiye e-posta gönderildi.", "success")
        return redirect(url_for('admin.admin_send_email_mandatory'))

    return render_template(
        'admin/admin-send-email.html',
        target="Zorunlu izin verenler",
        templates=templates,
        selected_template=selected_template,
        subject=subject,
        variables=variables,
        variable_map=variable_map
    )

@admin_bp.route('/supersecretadmin/send-email/all', methods=['GET', 'POST'])
def admin_send_email_all():
    if not is_admin_logged_in():
        return redirect(url_for('admin.admin_login'))

    templates = list_email_templates()
    selected_template = request.args.get('template_name', '') or None
    subject = ""
    variables = []
    variable_map = {}

    if selected_template:
        template_path = os.path.join(EMAIL_TEMPLATES_DIR, secure_filename(selected_template))
        if os.path.exists(template_path):
            with open(template_path, encoding="utf-8") as f:
                template_content = f.read()
            variables = extract_template_variables(template_content)

    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        template_name = request.form.get('template_name', '').strip()
        variable_map = {}
        for key in request.form:
            if key.startswith('varmap_'):
                var = key.replace('varmap_', '')
                variable_map[var] = request.form[key]

        if not subject or not template_name:
            flash("Konu ve şablon seçimi zorunludur.", "danger")
            return redirect(url_for('admin.admin_send_email_all'))

        template_path = os.path.join(EMAIL_TEMPLATES_DIR, secure_filename(template_name))
        if not os.path.exists(template_path):
            flash("Seçilen şablon bulunamadı.", "danger")
            return redirect(url_for('admin.admin_send_email_all'))

        with open(template_path, encoding="utf-8") as f:
            template_content = f.read()

        variables = extract_template_variables(template_content)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, uuid FROM users WHERE news_permission = 1 AND mandatory_email_permission = 1")
        users = cursor.fetchall()
        conn.close()

        sent_count = 0
        for user in users:
            context = {}
            for var in variables:
                field = variable_map.get(var, var)
                context[var] = user[field] if field in user.keys() else ""
            body = render_template_string(template_content, **context)
            if send_gmail_smtp(user["email"], subject, body):
                sent_count += 1

        flash(f"Her şeye izin veren {len(users)} kullanıcıdan {sent_count} kişiye e-posta gönderildi.", "success")
        return redirect(url_for('admin.admin_send_email_all'))

    return render_template(
        'admin/admin-send-email.html',
        target="Her şeye izin verenler",
        templates=templates,
        selected_template=selected_template,
        subject=subject,
        variables=variables,
        variable_map=variable_map
    )
