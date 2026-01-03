from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session, g
)
from werkzeug.security import generate_password_hash, check_password_hash
from .utils import (
    is_valid_email, is_medium_strong_password, get_serializer,
    send_reset_password_email, update_verification_sent_time,
    update_verification_token_and_time, get_db, get_user_by_email,
    get_user_by_id, add_auth_log, create_user, get_client_ip,
    get_user_by_verify_token, set_user_verified,
    send_verification_email, send_welcome_email
)
from functools import wraps
from datetime import datetime
from itsdangerous import SignatureExpired, BadSignature
import uuid

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Lütfen giriş yapın.", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = get_user_by_id(user_id)

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("Başarıyla çıkış yaptınız.", "success")
    return redirect(url_for('auth.login'))

@auth_bp.route('/please-verificate')
def please_verificate():
    return render_template('auth/please_verificate.html')

@auth_bp.route('/resend-verification', methods=['POST'])
@login_required
def resend_verification():
    user_id = g.user['id']
    user = get_user_by_id(user_id)

    if user['is_verified'] == 1:
        flash("Hesabınız zaten doğrulanmış.", "info")
        return redirect(url_for('panel'))

    last_sent = user['last_verification_sent']
    now = datetime.utcnow()

    if last_sent:
        try:
            last_sent_dt = datetime.strptime(last_sent, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            last_sent_dt = datetime.strptime(last_sent, "%Y-%m-%d %H:%M:%S")

        if (now - last_sent_dt).total_seconds() < 300:
            kalan = int(300 - (now - last_sent_dt).total_seconds())
            flash(f"Lütfen {kalan//60} dakika {kalan%60} saniye sonra tekrar deneyin.", "warning")
            return redirect(url_for('auth.please_verificate'))

    new_token = update_verification_token_and_time(user_id)
    user = get_user_by_id(user_id)

    send_verification_email(user['email'], user['name'], user['verify_token'])

    flash("Doğrulama e-postası tekrar gönderildi.", "success")
    return redirect(url_for('auth.please_verificate'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = get_user_by_email(email)
        if not user:
            flash("Bu e-posta ile kayıtlı bir kullanıcı bulunamadı.", "danger")
            return render_template('auth/forgot_password.html')

        serializer = get_serializer()
        token = serializer.dumps(email, salt='reset-password')
        send_reset_password_email(user['email'], user['name'], token)

        flash("Şifre sıfırlama bağlantısı e-posta adresinize gönderildi.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    serializer = get_serializer()
    try:
        email = serializer.loads(token, salt='reset-password', max_age=1800)
    except SignatureExpired:
        flash("Şifre sıfırlama bağlantısının süresi dolmuş.", "danger")
        return redirect(url_for('auth.forgot_password'))
    except BadSignature:
        flash("Geçersiz veya bozuk bağlantı.", "danger")
        return redirect(url_for('auth.forgot_password'))

    user = get_user_by_email(email)
    if not user:
        flash("Kullanıcı bulunamadı.", "danger")
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        password_confirm = request.form.get('passwordConfirm', '')

        if not password or not password_confirm:
            flash("Lütfen tüm alanları doldurun.", "danger")
            return render_template('auth/reset_password.html')

        if password != password_confirm:
            flash("Şifreler eşleşmiyor.", "danger")
            return render_template('auth/reset_password.html')

        is_strong, msg = is_medium_strong_password(password)
        if not is_strong:
            flash(msg, "danger")
            return render_template('auth/reset_password.html')

        password_hash = generate_password_hash(password)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = ? WHERE email = ?", (password_hash, email))
        conn.commit()
        conn.close()

        flash("Şifreniz başarıyla güncellendi. Giriş yapabilirsiniz.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if g.user:
        return redirect(url_for('panel'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password_confirm = request.form.get('passwordConfirm', '')
        terms_accept = request.form.get('termsAccept', '')
        news_permission = request.form.get('newsPermission', '')  # Artık zorunlu değil
        mandatory_email_permission = request.form.get('mandatoryEmailPermission', '')

        # Form validasyonu
        if not name or not email or not password or not password_confirm:
            flash("Lütfen tüm alanları doldurunuz.", "danger")
            return render_template('auth/register.html')

        if not is_valid_email(email):
            flash("Sadece belirli e-posta adresleri ile kayıt olunabilir.", "danger")
            return render_template('auth/register.html')

        is_strong, msg = is_medium_strong_password(password)
        if not is_strong:
            flash(msg, "danger")
            return render_template('auth/register.html')

        if password != password_confirm:
            flash("Girdiğiniz şifreler eşleşmiyor.", "danger")
            return render_template('auth/register.html')

        if not terms_accept:
            flash("Kullanım koşullarını kabul etmelisiniz.", "danger")
            return render_template('auth/register.html')

        if not mandatory_email_permission:
            flash("Zorunlu e-posta bildirimleri için izin vermelisiniz.", "danger")
            return render_template('auth/register.html')

        if get_user_by_email(email):
            flash("Bu e-posta adresi zaten kullanılıyor.", "danger")
            return render_template('auth/register.html')

        ip_address = get_client_ip()

        try:
            verify_token = str(uuid.uuid4())
            user_uuid = create_user(
                name, email, password, ip_address,
                int(bool(news_permission)), int(bool(mandatory_email_permission)),
                verify_token
            )
            send_verification_email(email, name, verify_token)
            add_auth_log(email, ip_address, "register", "success", "Kayıt başarılı")
            flash("Kayıt işleminiz başarıyla tamamlandı! Lütfen e-posta adresinizi doğrulayın.", "success")
            return redirect(url_for('auth.login'))
        except Exception as e:
            add_auth_log(email, ip_address, "register", "fail", f"Kayıt hatası: {str(e)}")
            flash(f"Kayıt sırasında bir hata oluştu: {str(e)}", "danger")
            print(f"Kayıt hatası: {str(e)}")

    return render_template('auth/register.html')

@auth_bp.route('/verify/<token>')
def verify_email(token):
    user = get_user_by_verify_token(token)
    if not user:
        return render_template('auth/verification_failed.html')
    set_user_verified(user['id'])
    send_welcome_email(user['email'], user['name'])
    return render_template('auth/verified.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('panel'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        ip_address = get_client_ip()
        user = get_user_by_email(email)

        if user and check_password_hash(user['password_hash'], password):
            if 'is_verified' in user.keys() and user['is_verified'] != 1:
                session.clear()
                session['user_id'] = user['id']
                add_auth_log(email, ip_address, "login", "fail", "E-posta doğrulanmamış")
                return redirect(url_for('auth.please_verificate'))
            session.clear()
            session['user_id'] = user['id']
            add_auth_log(email, ip_address, "login", "success", "Giriş başarılı")
            flash("Başarıyla giriş yaptınız!", "success")
            return redirect(url_for('panel'))
        else:
            add_auth_log(email, ip_address, "login", "fail", "Geçersiz e-posta veya şifre")
            flash("Geçersiz e-posta veya şifre.", "danger")

    return render_template('auth/login.html')

