# ===========================
# 🔧 Standart Kütüphaneler
# ===========================
import os
import sys
import re
import json
import uuid
import sqlite3
import cv2
import pytesseract
import unicodedata
import bcrypt
import smtplib
import requests
import threading
import time
from datetime import datetime, timedelta
from functools import wraps
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ===========================
# 🧪 3. Parti Kütüphaneler
# ===========================
import pandas as pd
import openpyxl
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, abort, redirect, url_for,
    flash, render_template_string, session, g, jsonify, Response
)

# ===========================
# ⚙️ Ortam Değişkenlerini Yükle (BURAYA TAŞINDI)
# ===========================
load_dotenv()  # .env dosyasını yükle

from flask_login import login_required
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from blueprints.admin import admin_bp
from blueprints.auth.auth import auth_bp

# ===========================
# 📦 Proje Modülleri
# ===========================
from modules.sonuclar import (
    get_all_denemeler,
    get_denemeler_by_tur,
    hesapla_istatistikler
)
from modules.data_reader import (
    get_genel_bilgiler,
    get_ders_istatistikleri,
    get_zaman_serisi,
    get_cevaplama_istatistikleri,
    get_son_denemeler,
    get_en_yuksek_net,
    get_deneme_sonuclari
)
from modules.results_reader import hesapla_sonuclar
from modules.optik_reader_web import read_answers_and_stats
from modules.evaluation import hesapla_sonuc
from modules.excel_writer import (
    write_genel_bilgiler,
    write_cevaplar,
    write_sonuclar
)
from groq import Groq
from blueprints.auth.utils import check_and_update_user_table_schema

# ===========================
# ⚙️ Ortam Değişkenlerini Yükle
# ===========================
# load_dotenv()  # .env dosyasını yükle <-- BU SATIR YUKARI TAŞINDI

# Flask gizli anahtarını .env'den al
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
csrf = CSRFProtect(app)
# Güvenli oturum ayarları
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,  # HTTPS şart
    SESSION_COOKIE_SAMESITE='Lax'
)

# Upload klasörü
UPLOAD_DIR = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR

# Veritabanı yolu: app.py'nin bulunduğu dizinde veritabani.db
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'veritabani.db')

app.config['BASE_URL'] = None  # Başlangıçta boş

@app.before_request
def set_base_url():
    if app.config['BASE_URL'] is None:
        url_root = request.url_root  # örn: 'http://localhost:5000/'
        app.config['BASE_URL'] = url_root.rstrip('/')
        print(f"BASE_URL dinamik olarak ayarlandı: {app.config['BASE_URL']}")




# --- Yardımcı Fonksiyonlar ---
def get_client_ip():
    """Kullanıcının gerçek IP adresini almak için yardımcı fonksiyon"""
    # Proxy arkasında çalışırken X-Forwarded-For header'ını kontrol et
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0].split(',')[0]
    # X-Real-IP header'ı varsa kullan (Nginx)
    elif request.headers.get("X-Real-IP"):
        ip = request.headers.get("X-Real-IP")
    # Direkt bağlantı için remote_addr kullan
    else:
        ip = request.remote_addr or "unknown"

    # Localhost IP'sini tespit et ve daha anlamlı bir değerle değiştir
    if ip == "127.0.0.1" or ip == "::1":
        # Eğer geliştirme ortamındaysak, gerçek IP adresini almaya çalış
        try:
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if local_ip != "127.0.0.1":
                ip = local_ip
        except:
            # Hata durumunda "local-development" olarak kaydet
            ip = "local-development"

    return ip

def normalize_subject(subject):
    """
    Ders adlarını JavaScript'teki normalizeSubject fonksiyonuyla
    tam olarak aynı şekilde normalize eder. Bu, tutarlılık için kritiktir.
    """
    if not subject or not isinstance(subject, str):
        return ''

    # NFD (Normalization Form D) ile karakterleri ayır (örn: 'ö' -> 'o' + '¨')
    # Bu, aksanları daha güvenilir bir şekilde kaldırmayı sağlar.
    normalized = ''.join(c for c in unicodedata.normalize('NFD', subject) if unicodedata.category(c) != 'Mn')

    # Türkçe karakterleri ve boşlukları değiştir
    normalized = normalized.replace('ç', 'c').replace('ğ', 'g').replace('ı', 'i') \
        .replace('ö', 'o').replace('ş', 's').replace('ü', 'u') \
        .replace(' ', '_')

    # Sadece alfanümerik karakterler ve alt çizgi kalsın
    normalized = re.sub(r'[^\w_]', '', normalized).lower()

    return normalized


def get_deneme_ozeti(user_uuid):
    """
    Kullanıcının deneme özetini getirir (Senin scriptindeki mantıkla güncellendi)
    """
    # get_all_denemeler fonksiyonunun app.py içinde tanımlı olduğundan emin ol
    # veya modules.sonuclar importunu kullan
    try:
        denemeler = get_all_denemeler(user_uuid) 
        
        if denemeler:
            # Tarihe göre sırala (en yeni en üstte)
            son_deneme = sorted(denemeler, key=lambda x: x['tarih'], reverse=True)[0]
            
            # Detayları stringe çevir
            detay_str = ", ".join([f"{d['ders']}: {d['net']} net" for d in son_deneme.get('detaylar', [])])
            
            return (f"Son denemen: {son_deneme['deneme_adi']} ({son_deneme['tarih']}) - "
                    f"Toplam Net: {son_deneme.get('toplam_net', 0)}. Dersler: {detay_str}")
    except Exception as e:
        print(f"Deneme özeti hatası: {e}")

    return "Henüz deneme sonucu yok."

def create_system_prompt(deneme_ozet, not_ozeti):
    """
    Senin yeni ve geliştirilmiş prompt yapın.
    """
    return f"""Sen bir YKS koçusun.

Görevin, kullanıcının verdiği son mesaja **öncelikli olarak yanıt vermek** ve gerekirse önceki verilerle ilişkilendirmektir.

KURALLAR:
- Deneme özeti ve kullanıcı notları rehberin olacak ama asıl odak **kullanıcının yazdıklarıdır.**
- Konuyla ilgisiz genel tavsiyeler verme.
- Cevapların 3-4 cümle olsun, samimi ve motive edici ol.
- Kullanıcı henüz belirtmediyse, hedef, uyku düzeni gibi konuları doğal sorularla öğrenebilirsin.
- Kullanıcı meslek veya bölüm belirtmedikçe tahminde bulunma.

📚 SINAV BİLGİLERİ:
- TYT: 120 soru, 165 dakika (Türkçe, Matematik, Sosyal Bilgiler, Fen Bilimleri)
- AYT: 160 soru, 180 dakika (Sayısal, Eşit Ağırlık, Sözel alanlarına göre ders dağılımı)
- 4 yanlış 1 doğruyu götürür.

📊 Son deneme özeti:
{deneme_ozet}

🧠 Kullanıcı notları:
{not_ozeti}

🔁 NOT KAYDETME:
Kullanıcı bir hedef, alışkanlık veya motivasyon bilgisi verirse, cevabının başına 
'Koç, bu notu hatırla: <not>' ifadesini ekle. 
Bu not, sonraki cevaplarda kullanman için kendi hafızanda saklanacak.

Son olarak: Kullanıcıya birebir ilgi gösteren, ihtiyaçlarına göre yol gösteren ve motive eden bir koç gibi konuş."""

def extract_and_save_notes(text, user_uuid):
    """AI yanıtından notları ayıkla ve veritabanına kaydet"""
    import re
    # Senin regex mantığın
    notlar = re.findall(r"Koç, bu notu hatırla: (.+?)(?:\n|$)", text)
    for note in notlar:
        add_koc_note(user_uuid, note.strip())

# Debug modu - geliştirme sırasında açılabilir
DEBUG_MODE = False

# Varsayılan öğrenci cevap deseni
DEFAULT_STUDENT_ANSWER_PATTERN = ['A', 'B', 'C', 'D', 'E']


def generate_pattern_answers(soru_sayisi):
    """Belirli bir desen kullanarak otomatik cevaplar üretir"""
    pattern = DEFAULT_STUDENT_ANSWER_PATTERN
    return [pattern[i % len(pattern)] for i in range(soru_sayisi)]


def normalize_cevaplar(text):
    """Metin içindeki cevapları bulup normalize eder. Örneğin '1-A, 2:B, 3C' gibi metinlerden {'1':'A', '2':'B', '3':'C'} sözlüğü oluşturur."""
    text = text.upper()

    # Olası cevap formatları: "1-A", "1:A", "1.A", "1)A", "1A", vs.
    pattern = r'(\d+)[\s\-\.:,;\)\}]*([A-E])'
    matches = re.findall(pattern, text)

    # Eğer hiç eşleşme bulunamazsa, her karakteri bir cevap olarak değerlendir
    if not matches:
        text = re.sub(r'[^A-E]', '', text)  # Sadece A-E karakterlerini bırak
        # Eğer 40'tan fazla karakter varsa, ilk 40'ını al
        text = text[:40]
        return {str(i + 1): c for i, c in enumerate(text)}

    # Eşleşmelerden sözlük oluştur
    return {soru: cevap for soru, cevap in matches}


UPLOAD_DIR = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR

current_deneme_id = 1  # Bu örnekte basit tutuldu, gerçek uygulamada DB veya kalıcı kayıt tercih edilir




def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user:
            flash("Giriş yapmalısınız.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/panel')
@login_required
def panel():
    if not g.user or ('is_verified' in g.user.keys() and g.user['is_verified'] != 1):
        return redirect(url_for('please_verificate'))
    return render_template('panel.html')


# --- Gizlilik Politikası ve Kullanım Koşulları Sayfaları ---
@app.route('/gizlilik')
def gizlilik():
    return render_template('gizlilik.html')


@app.route('/kullanim_kosullari')
def kullanim_kosullari():
    return render_template('kullanim_kosullari.html')


# --- Çerez Politikası Sayfası ---
@app.route('/cerez-politikasi')
def cerez_politikasi():
    return render_template('cerez-politikasi.html')


# Yeni deneme ekleme sayfası (GET ve POST)
@app.route('/yeni-deneme', methods=['GET', 'POST'])
@login_required
def yeni_deneme():
    # TYT ve AYT için dersler ve soru sayıları
    TYT_DERSLER = [
        ('Türkçe', 40),
        ('Sosyal Bilimler', 20),
        ('Temel Matematik', 40),
        ('Fen Bilimleri', 20)
    ]
    AYT_DERSLER = [
        ('Matematik', 40),
        ('Fen Bilimleri', 40),
        ('Türk Dili ve Edebiyatı – Sosyal Bilimler 1', 40),
        ('Sosyal Bilimler 2', 40)
    ]

    # POST isteği: Formdan gelen verileri işle
    if request.method == 'POST':
        # --- DEBUG: Gelen tüm form verisini konsola yazdır ---
        print("--- YENI DENEME FORM VERISI ---")
        print(json.dumps(request.form.to_dict(), indent=2, ensure_ascii=False))
        print("-----------------------------")

        deneme_adi = request.form.get('deneme_adi', '').strip()
        tarih = request.form.get('tarih', '').strip()
        tur = request.form.get('tur', '').strip().upper()

        if not deneme_adi or not tarih or tur not in ['TYT', 'AYT']:
            flash("Lütfen tüm alanları doğru bir şekilde doldurun.", "danger")
            return redirect(url_for('yeni_deneme'))

        all_dersler = TYT_DERSLER if tur == 'TYT' else AYT_DERSLER

        # Orijinal ders adlarını ve normalleştirilmiş hallerini eşleştiren bir harita oluştur
        ders_map = {normalize_subject(ders_adi): ders_adi for ders_adi, _ in all_dersler}

        cevap_anahtari = {ders: [''] * s for ders, s in all_dersler}
        ogrenci_cevaplari = {ders: [''] * s for ders, s in all_dersler}

        # Formdan gelen tüm verileri işle
        for key, value in request.form.items():
            value = value.strip().upper()
            if not value:
                continue

            parts = key.split('_')
            if len(parts) < 3:
                continue

            prefix = parts[0]  # 'cevap' veya 'ogrenci'
            form_ders_key = '_'.join(parts[1:-1])  # Birden fazla kelimeli dersler için (örn: sosyal_bilimler)
            soru_no_str = parts[-1]

            if not soru_no_str.isdigit():
                continue

            soru_idx = int(soru_no_str) - 1

            # Formdan gelen ders anahtarın�� orijinal ders adına çevir
            original_ders_adi = ders_map.get(form_ders_key)
            if not original_ders_adi:
                print(f"[UYARI] Eşleşmeyen form anahtarı: {form_ders_key}")
                continue  # Eşleşmeyen bir ders ise atla

            soru_sayisi = dict(all_dersler)[original_ders_adi]
            if not (0 <= soru_idx < soru_sayisi):
                continue

            if prefix == 'cevap':
                if value in ['A', 'B', 'C', 'D', 'E']:
                    cevap_anahtari[original_ders_adi][soru_idx] = value
            elif prefix == 'ogrenci':
                if value in ['A', 'B', 'C', 'D', 'E']:
                    ogrenci_cevaplari[original_ders_adi][soru_idx] = value

        # DEBUG_MODE açıksa ve cevap anahtarı tamamen boşsa, öğrenci cevaplarını kopyala
        if DEBUG_MODE:
            for ders, sorular in cevap_anahtari.items():
                if all(x == '' for x in sorular) and any(y != '' for y in ogrenci_cevaplari[ders]):
                    cevap_anahtari[ders] = list(ogrenci_cevaplari[ders])
                    flash(f"[DEBUG] {ders} için cevap anahtarı öğrenci cevaplarından kopyalandı.", "warning")

        # Boş dersler varsa ve debug kapalıysa uyarı ver
        empty_subjects = [d for d, s in cevap_anahtari.items() if all(x == '' for x in s)]
        if empty_subjects and not DEBUG_MODE:
            flash(f"Şu dersler için cevap anahtarı boş: {', '.join(empty_subjects)}", "danger")
            # Hatalı durumu kullanıcıya göstermek için formu tekrar render et
            return render_template('yeni_deneme.html')

        # Veritabanına kaydetme işlemleri
        try:
            deneme_id = str(uuid.uuid4())
            sonuc = hesapla_sonuc(cevap_anahtari, ogrenci_cevaplari, tur)
            ogrenci_uuid = g.user['uuid']

            write_genel_bilgiler(ogrenci_uuid, deneme_id, deneme_id, deneme_adi, tarih, tur)
            write_cevaplar(ogrenci_uuid, deneme_id, cevap_anahtari, ogrenci_cevaplari, tur)
            write_sonuclar(ogrenci_uuid, deneme_id, sonuc, tur)

            flash(f"{deneme_adi} başarıyla kaydedildi.", "success")
            return redirect(url_for('deneme_detay', tur=tur.lower(), deneme_id=deneme_id))

        except Exception as e:
            app.logger.error(f"Deneme kayıt hatası: {e}", exc_info=True)
            flash(f"Kayıt sırasında bir hata oluştu: {e}", "danger")
            return redirect(url_for('yeni_deneme'))

    # GET isteği: Sayfa ilk yüklendiğinde
    return render_template('yeni_deneme.html')


@app.route('/denemeler')
@login_required
def denemeler():
    import sqlite3

    denemeler_listesi = []
    db_path = os.path.join(os.getcwd(), 'veritabani.db')
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        ogrenci_uuid = g.user['uuid']  # Kullanıcının uuid'sı

        for tur in ['tyt', 'ayt']:
            tablo = f"genel_bilgiler_{tur}"
            if cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tablo,)).fetchone():
                cursor.execute(f"SELECT * FROM {tablo} WHERE ogrenci_uuid = ?", (ogrenci_uuid,))
                rows = cursor.fetchall()
                for row in rows:
                    denemeler_listesi.append({
                        'deneme_adi': row['deneme_adi'],
                        'tarih': row['tarih'],
                        'tur': row['tur'].upper(),
                        'deneme_id': row['deneme_id'],
                        'ogrenci_uuid': row['ogrenci_uuid'],
                        'uuid': row['uuid']
                    })
        conn.close()
    except Exception as e:
        flash(f"Denemeler alınırken hata oluştu: {str(e)}", "danger")

    if not denemeler_listesi:
        flash("Hiç deneme bulunamadı.", "warning")

    return render_template('denemeler.html', denemeler=denemeler_listesi)


@app.route('/deneme/<tur>/<deneme_id>')
@login_required
def deneme_detay(tur, deneme_id):
    import sqlite3

    tur = tur.lower()
    if tur not in ['tyt', 'ayt']:
        return "Geçersiz deneme türü. Sadece TYT veya AYT desteklenir.", 400

    ogrenci_uuid = g.user['uuid']  # Kullanıcının uuid'sı
    db_path = os.path.join(os.getcwd(), 'veritabani.db')
    cevaplar_tablosu = f"cevaplar_{tur}"
    genel_bilgiler_tablosu = f"genel_bilgiler_{tur}"
    tam_sonuc_tablosu = f"tam_sonuc_{tur}"

    # Ders adı normalize fonksiyonu (Din Kültürü varyasyonları için)
    def normalize_ders_adi(ders):
        d = ders.strip().lower()
        if d in ['din', 'din kültürü', 'din kültürü ve ahlak bilgisi', 'din kültürü ve ahlak',
                 'din kültürü ve ahlak bilgisi']:
            return 'Din Kültürü ve Ahlak Bilgisi'
        return ders

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Genel bilgiler
        cursor.execute(f"SELECT * FROM {genel_bilgiler_tablosu} WHERE deneme_id = ? AND ogrenci_uuid = ?",
                       (deneme_id, ogrenci_uuid))
        deneme_row = cursor.fetchone()
        if not deneme_row:
            return f"Deneme bulunamadı: {deneme_id}", 404

        deneme = {
            'deneme_adi': deneme_row['deneme_adi'],
            'tarih': str(deneme_row['tarih'])[:10],
            'deneme_id': deneme_id
        }
        uuid = deneme_row['uuid']

        # Cevaplar
        cursor.execute(f"SELECT * FROM {cevaplar_tablosu} WHERE uuid = ? AND ogrenci_uuid = ?",
                       (uuid, ogrenci_uuid))
        cevaplar = []
        for row in cursor.fetchall():
            ders_norm = normalize_ders_adi(row['ders'])
            cevap_dict = {
                'soru_no': int(row['soru_no']),
                'ders': ders_norm,
                'dogru_cevap': (row['dogru_cevap'] or '').strip().upper(),
                'ogrenci_cevap': (row['ogrenci_cevap'] or '').strip().upper()
            }
            if cevap_dict['ogrenci_cevap'] in ['', 'NAN', 'NONE']:
                cevap_dict['ogrenci_cevap'] = ''
            if cevap_dict['dogru_cevap'] in ['', 'NAN', 'NONE']:
                cevap_dict['dogru_cevap'] = ''
            cevaplar.append(cevap_dict)

        # Sonuçlar
        cursor.execute(f"SELECT * FROM {tam_sonuc_tablosu} WHERE uuid = ? AND ogrenci_uuid = ?",
                       (uuid, ogrenci_uuid))
        bolum_sonuc = {}
        toplam_dogru = toplam_yanlis = toplam_bos = toplam_net = toplam_soru = 0

        # Alt ders isimleri (ana dersler hariç tutulacak)
        tyt_alt_dersler = [
            'Tarih', 'Coğrafya', 'Felsefe', 'Din Kültürü ve Ahlak Bilgisi',
            'Fizik', 'Kimya', 'Biyoloji',
            'Türkçe', 'Matematik'
        ]
        ayt_alt_dersler = [
            'Türk Dili ve Edebiyatı', 'Tarih-1', 'Coğrafya-1',
            'Tarih-2', 'Coğrafya-2', 'Felsefe Grubu', 'Din Kültürü ve Ahlak Bilgisi',
            'Matematik', 'Fizik', 'Kimya', 'Biyoloji'
        ]

        # Sonuçları normalize ederek ekle
        for row in cursor.fetchall():
            ders = normalize_ders_adi(row['ders'])
            # Eğer hem "Din Kültürü" hem "Din Kültürü ve Ahlak Bilgisi" varsa birleştir
            if ders in ['Din Kültürü', 'Din Kültürü ve Ahlak Bilgisi']:
                ders = 'Din K��ltürü ve Ahlak Bilgisi'
            dogru = row['dogru'] or 0
            yanlis = row['yanlis'] or 0
            bos = row['bos'] or 0
            net = row['net'] or 0.0
            bolum_sonuc[ders] = {
                'dogru': dogru,
                'yanlis': yanlis,
                'bos': bos,
                'net': net
            }
            # Sadece alt dersler toplam hesaba katılsın
            if tur == 'tyt':
                if ders in tyt_alt_dersler:
                    toplam_dogru += dogru
                    toplam_yanlis += yanlis
                    toplam_bos += bos
                    toplam_net += net
                    toplam_soru += row['toplam'] or 0
            elif tur == 'ayt':
                if ders in ayt_alt_dersler:
                    toplam_dogru += dogru
                    toplam_yanlis += yanlis
                    toplam_bos += bos
                    toplam_net += net
                    toplam_soru += row['toplam'] or 0

        toplam_sonuc = {
            'dogru': toplam_dogru,
            'yanlis': toplam_yanlis,
            'bos': toplam_bos,
            'net': round(toplam_net, 2),
            'toplam_soru': toplam_soru
        }

        conn.close()

    except Exception as e:
        print(f"[HATA] Veritabanı hatası: {e}")
        return f"Deneme verileri okunamadı: {str(e)}", 500

    print(f"[DEBUG] Deneme: {deneme_id}, Tür: {tur}")
    print(f"[DEBUG] Bulunan cevap sayısı: {len(cevaplar)}")
    print(f"[DEBUG] Bölüm sonuçları: {list(bolum_sonuc.keys())}")

    return render_template(
        'deneme_detay.html',
        tur=tur,
        deneme=deneme,
        cevaplar=cevaplar,
        bolum_sonuc=bolum_sonuc,
        toplam_sonuc=toplam_sonuc
    )


@app.route('/deneme/sil/<tur>/<deneme_id>', methods=['POST'])
@login_required
def deneme_sil(tur, deneme_id):
    import sqlite3

    tur = tur.lower()
    db_path = os.path.join(os.getcwd(), 'veritabani.db')
    deleted = False
    ogrenci_uuid = g.user['uuid']  # Kullanıcının uuid'sı

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. genel_bilgiler tablosundan uuid ve ogrenci_uuid bul
        genel_bilgiler_tablosu = f"genel_bilgiler_{tur}"
        cursor.execute(f"SELECT uuid FROM {genel_bilgiler_tablosu} WHERE deneme_id = ? AND ogrenci_uuid = ?",
                       (deneme_id, ogrenci_uuid))
        row = cursor.fetchone()
        if not row:
            flash("Silinecek deneme bulunamadı", "warning")
            return redirect(url_for('denemeler', tur=tur.upper()))
        uuid = row[0]

        # 2. genel_bilgiler tablosundan sil
        cursor.execute(f"DELETE FROM {genel_bilgiler_tablosu} WHERE deneme_id = ? AND ogrenci_uuid = ?",
                       (deneme_id, ogrenci_uuid))

        # 3. cevaplar tablosundan sil
        cevaplar_tablosu = f"cevaplar_{tur}"
        cursor.execute(f"DELETE FROM {cevaplar_tablosu} WHERE uuid = ? AND ogrenci_uuid = ?",
                       (uuid, ogrenci_uuid))

        # 4. tam_sonuc tablosundan sil
        tam_sonuc_tablosu = f"tam_sonuc_{tur}"
        cursor.execute(f"DELETE FROM {tam_sonuc_tablosu} WHERE uuid = ? AND ogrenci_uuid = ?",
                       (uuid, ogrenci_uuid))

        conn.commit()
        deleted = True
        flash(f"{tur.upper()} türündeki deneme başarıyla silindi", "success")
    except Exception as e:
        flash(f"Silme sırasında hata oluştu: {str(e)}", "danger")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()

    if not deleted:
        flash("Silinecek deneme verileri bulunamadı", "warning")

    return redirect(url_for('denemeler', tur=tur.upper()))


@app.route('/deneme/duzenle/<tur>/<deneme_id>', methods=['GET', 'POST'])
@login_required
def deneme_duzenle(tur, deneme_id):
    import sqlite3

    tur = tur.lower()
    db_path = os.path.join(os.getcwd(), 'veritabani.db')
    ogrenci_uuid = g.user['uuid']  # Kullanıcının uuid'sı

    ders_adi_harita = {
        'Türkçe': 'Turkce',
        'Sosyal Bilimler': 'Sosyal',
        'Temel Matematik': 'Matematik',
        'Fen Bilimleri': 'Fen'
    }
    kisa_to_tam = {v: k for k, v in ders_adi_harita.items()}
    dersler = list(ders_adi_harita.keys())

    if request.method == 'POST':
        yeni_ad = request.form.get('deneme_adi', '').strip()
        yeni_tarih = request.form.get('tarih', '').strip()

        if not yeni_ad or not yeni_tarih:
            flash("Lütfen tüm gerekli alanları doldurunuz", "danger")
            return redirect(url_for('deneme_duzenle', tur=tur.upper(), deneme_id=deneme_id))

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Genel bilgileri güncelle
            genel_bilgiler_tablosu = f"genel_bilgiler_{tur}"
            cursor.execute(f"SELECT * FROM {genel_bilgiler_tablosu} WHERE deneme_id = ? AND ogrenci_uuid = ?",
                           (deneme_id, ogrenci_uuid))
            row = cursor.fetchone()
            if not row:
                flash("Düzenlenecek deneme bulunamadı", "danger")
                conn.close()
                return redirect(url_for('denemeler', tur=tur.upper()))

            uuid = row[2]  # uuid sütunu
            ogrenci_uuid = row[1]  # ogrenci_uuid sütunu

            cursor.execute(f"UPDATE {genel_bilgiler_tablosu} SET deneme_adi = ?, tarih = ? WHERE deneme_id = ? AND ogrenci_uuid = ?",
                           (yeni_ad, yeni_tarih, deneme_id, ogrenci_uuid))

            # Cevapları güncelle
            cevaplar_tablosu = f"cevaplar_{tur}"
            cursor.execute(f"DELETE FROM {cevaplar_tablosu} WHERE uuid = ? AND ogrenci_uuid = ?",
                           (uuid, ogrenci_uuid))

            data = []
            for form_ders_kisa in ders_adi_harita.values():
                for i in range(1, 41):
                    anahtar = request.form.get(f'cevap_{form_ders_kisa}_{i}', '').strip().upper()
                    ogrenci = request.form.get(f'ogrenci_{form_ders_kisa}_{i}', '').strip().upper()

                    anahtar = anahtar if anahtar in ['A', 'B', 'C', 'D', 'E'] else ''
                    ogrenci = ogrenci if ogrenci in ['A', 'B', 'C', 'D', 'E'] else ''

                    data.append((ogrenci_uuid, uuid, form_ders_kisa, i, anahtar, ogrenci))

            cursor.executemany(
                f"INSERT INTO {cevaplar_tablosu} (ogrenci_uuid, uuid, ders, soru_no, dogru_cevap, ogrenci_cevap) VALUES (?, ?, ?, ?, ?, ?)",
                data
            )

            # Cevap anahtarı ve öğrenci cevapları sözlüklerini oluştur
            cevap_anahtari = {k: [''] * 40 for k in dersler}
            ogrenci_cevaplari = {k: [''] * 40 for k in dersler}
            for row in data:
                ders_kisa = row[2]
                tam_ders_adi = kisa_to_tam.get(ders_kisa, ders_kisa)
                soru_idx = row[3] - 1
                if 0 <= soru_idx < 40:
                    cevap_anahtari[tam_ders_adi][soru_idx] = row[4]
                    ogrenci_cevaplari[tam_ders_adi][soru_idx] = row[5]

            # Sonuçları hesapla ve güncelle
            from modules.evaluation import hesapla_sonuc
            sonuc = hesapla_sonuc(cevap_anahtari, ogrenci_cevaplari, tur)
            tam_sonuc_tablosu = f"tam_sonuc_{tur}"
            cursor.execute(f"DELETE FROM {tam_sonuc_tablosu} WHERE uuid = ? AND ogrenci_uuid = ?", (uuid, ogrenci_uuid))
            sonuc_data = []
            from datetime import datetime
            now = datetime.now().isoformat()
            for k, v in sonuc.items():
                if k == "Toplam":
                    continue
                sonuc_data.append((
                    ogrenci_uuid, uuid, k, v['dogru'], v['yanlis'], v['bos'], v['net'], 40, now
                ))
            cursor.executemany(
                f"INSERT INTO {tam_sonuc_tablosu} (ogrenci_uuid, uuid, ders, dogru, yanlis, bos, net, toplam, tarih) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                sonuc_data
            )

            conn.commit()
            conn.close()
            flash("Deneme başarıyla güncellendi", "success")
            return redirect(url_for('deneme_detay', tur=tur, deneme_id=deneme_id))

        except Exception as e:
            flash(f"Düzenleme sırasında hata oluştu: {str(e)}", "danger")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return redirect(url_for('deneme_duzenle', tur=tur.upper(), deneme_id=deneme_id))

    # GET isteği: mevcut verileri oku
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        genel_bilgiler_tablosu = f"genel_bilgiler_{tur}"
        cevaplar_tablosu = f"cevaplar_{tur}"

        cursor.execute(f"SELECT * FROM {genel_bilgiler_tablosu} WHERE deneme_id = ? AND ogrenci_uuid = ?",
                       (deneme_id, ogrenci_uuid))
        deneme_row = cursor.fetchone()
        if not deneme_row:
            flash("Deneme bilgisi bulunamadı", "danger")
            conn.close()
            return redirect(url_for('denemeler', tur=tur.upper()))
        uuid = deneme_row['uuid']

        cursor.execute(f"SELECT * FROM {cevaplar_tablosu} WHERE uuid = ? AND ogrenci_uuid = ?",
                       (uuid, ogrenci_uuid))
        cevaplar_rows = cursor.fetchall()

        cevap_anahtari = {k: [''] * 40 for k in dersler}
        ogrenci_cevaplari = {k: [''] * 40 for k in dersler}
        for row in cevaplar_rows:
            ders_adi = row['ders']
            tam_ders = kisa_to_tam.get(ders_adi, ders_adi) if ders_adi in kisa_to_tam or ders_adi in dersler else None
            if tam_ders is None:
                app.logger.warning(f"Bilinmeyen ders ismi: {ders_adi}")
                continue
            soru_idx = int(row['soru_no']) - 1
            if 0 <= soru_idx < 40:
                cevap_anahtari[tam_ders][soru_idx] = row['dogru_cevap'] or ''
                ogrenci_cevaplari[tam_ders][soru_idx] = row['ogrenci_cevap'] or ''

        deneme = {
            'deneme_adi': deneme_row['deneme_adi'],
            'tarih': deneme_row['tarih']
        }
        conn.close()
    except Exception as e:
        flash(f"Deneme bilgisi yüklenirken hata oluştu: {str(e)}", "danger")
        deneme = {'deneme_adi': '', 'tarih': ''}
        cevap_anahtari = {k: [''] * 40 for k in dersler}
        ogrenci_cevaplari = {k: [''] * 40 for k in dersler}

    return render_template(
        'deneme_duzenle.html',
        tur=tur.upper(),
        deneme_id=deneme_id,
        deneme=deneme,
        cevap_anahtari=cevap_anahtari,
        ogrenci_cevaplari=ogrenci_cevaplari,
        dersler=dersler,
        ders_adi_harita=ders_adi_harita
    )


def delete_file_if_exists(path):
    """Dosya varsa siler"""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"Dosya silinemedi: {path} ({e})")


@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya seçilmedi'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Dosya seçilmedi'}), 400

    # Benzersiz dosya ismi oluştur
    ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4().hex}{ext if ext else '.jpg'}"
    static_uploads_dir = os.path.join('static', 'uploads')
    os.makedirs(static_uploads_dir, exist_ok=True)
    static_path = os.path.join(static_uploads_dir, unique_name)
    file.save(static_path)
    static_url = f"/static/uploads/{unique_name}"

    # 10 dakika sonra silmek için kuyruğa ekle
    schedule_delete(static_path, delay_sec=600)

    # Doğrudan cevap anahtarı ROI sayfasına yönlendir
    return jsonify({
        'redirect_url': url_for('select_roi_page', image=static_url, is_cevap_anahtari='true'),
        'image_path': static_path
    })


@app.route('/roi-secimi')
@login_required
def select_roi_page():
    image_url = request.args.get('image')
    ders = request.args.get('ders', '')  # İstersen ders parametresi de ekleyebilirsin
    if not image_url:
        return "Görsel URL belirtilmedi.", 400
    return render_template('select_roi.html', image_url=image_url, ders=ders)


@app.route('/ocr/web-region', methods=['POST'])
@login_required
def ocr_web_region():
    try:
        x = int(request.form['x'])
        y = int(request.form['y'])
        w = int(request.form['w'])
        h = int(request.form['h'])
        image_path = request.form['image_url'].lstrip('/')
        full_path = os.path.join(os.getcwd(), image_path)

        from modules import ocr
        metin = ocr.extract_text_from_region(full_path, x, y, w, h)

        # ROI işlemi tamamlandıktan sonra dosyayı hemen silme kaldırıldı
        # Dosya zaten upload sırasında silme kuyruğuna alınmış olacak

        return jsonify({'text': metin})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/parse-answers', methods=['POST'])
@login_required
def parse_answers():
    data = request.get_json()
    text = data.get('text', '')
    try:
        answers = normalize_cevaplar(text)  # Ayrıştırma fonksiyonun burada çağrılır
        # Örnek dönüş: {"1": "A", "2": "B", ...}
        return jsonify({'answers': answers})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route("/ogrenci-roi")
@login_required
def ogrenci_roi_page():
    image = request.args.get("image")
    return render_template("ogrenci_roi.html", image=image)


@app.route('/ogrenci-roi-veri', methods=['POST'])
@login_required
def ogrenci_roi_veri():
    try:
        x = int(request.form['x'])
        y = int(request.form['y'])
        w = int(request.form['w'])
        h = int(request.form['h'])
        image_url_path = request.form['image']
        ders = request.form['ders']

        # Dosya yolunu normalize et (Windows/Linux uyumlu)
        rel_path = image_url_path.replace('static/', '', 1).lstrip('/\\')
        image_fs_path = os.path.normpath(os.path.join('static', rel_path))

        if not os.path.exists(image_fs_path):
            return jsonify({"error": f"Görsel bulunamadı: {image_fs_path}"}), 400

        img = cv2.imread(image_fs_path)
        if img is None:
            return jsonify({"error": "Görsel okunamadı."}), 400

        from modules.optik_reader_web import read_answers_and_stats
        answers, stats = read_answers_and_stats(img, x, y, w, h)

        # Görseli hemen silme kaldırıldı, silme kuyruğuna ekleniyor
        schedule_delete(image_fs_path, delay_sec=600)

        return jsonify({
            "answers": answers,
            "stats": stats,
            "ders": ders
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/upload-optik", methods=["POST"])
@login_required
def upload_optik():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Dosya yok"}), 400

    # Benzersiz dosya ismi oluştur
    ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    static_uploads_dir = os.path.join('static', 'uploads')
    os.makedirs(static_uploads_dir, exist_ok=True)
    static_path = os.path.join(static_uploads_dir, unique_name)
    file.save(static_path)
    static_url = f"/static/uploads/{unique_name}"

    # 10 dakika sonra silmek için kuyruğa ekle
    schedule_delete(static_path, delay_sec=600)

    return jsonify({
        "redirect_url": url_for("ogrenci_roi_page") + f"?image={static_url}",
        "image_path": static_path
    })


@app.route('/api/istatistikler')
@login_required
def api_istatistikler():
    tur = request.args.get('tur')  # 'TYT', 'AYT' veya None
    zaman = request.args.get('zaman')  # '3m', '6m', 'all' gibi
    ogrenci_uuid = g.user['uuid']  # Kullanıcının uuid'sı

    try:
        istatistik = hesapla_istatistikler(tur=tur, zaman_araligi=zaman or "all", ogrenci_uuid=ogrenci_uuid)
        return jsonify(istatistik)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/deneme-detay/<deneme_id>', endpoint='deneme_detay_endpoint')
@login_required
def deneme_detay_api(deneme_id):
    import sqlite3
    ogrenci_uuid = g.user['uuid']  # Kullanıcının uuid'sı

    try:
        db_path = os.path.join(os.getcwd(), 'veritabani.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # genel_bilgiler tablosunda deneme_id ile arama yap
        cursor.execute("""
                       SELECT *
                       FROM genel_bilgiler_tyt
                       WHERE uuid = ?
                         AND ogrenci_uuid = ?
                       UNION ALL
                       SELECT *
                       FROM genel_bilgiler_ayt
                       WHERE uuid = ?
                         AND ogrenci_uuid = ?
                       """, (deneme_id, ogrenci_uuid, deneme_id, ogrenci_uuid))
        deneme_row = cursor.fetchone()
        if not deneme_row:
            return jsonify({'error': 'Deneme bulunamadı'}), 404

        tur = deneme_row['tur'].lower()
        genel_bilgiler = {
            'deneme_adi': deneme_row['deneme_adi'],
            'tarih': deneme_row['tarih'],
            'tur': deneme_row['tur'],
            'uuid': deneme_row['uuid']
        }

        # Sonuçları getir
        tam_sonuc_tablosu = f"tam_sonuc_{tur}"
        cursor.execute(f"SELECT * FROM {tam_sonuc_tablosu} WHERE uuid = ? AND ogrenci_uuid = ?",
                       (deneme_id, ogrenci_uuid))
        sonuclar = cursor.fetchall()
        if not sonuclar:
            return jsonify({'error': 'Deneme sonuçları bulunamadı'}), 404

        dersler = []
        toplam_net = 0
        for row in sonuclar:
            dersler.append({
                'ad': row['ders'],
                'net': float(row['net']),
                'dogru': int(row['dogru']),
                'yanlis': int(row['yanlis']),
                'bos': int(row['bos'])
            })
            toplam_net += row['net']

        response = {
            'deneme_adi': genel_bilgiler['deneme_adi'],
            'tarih': genel_bilgiler['tarih'],
            'tur': genel_bilgiler['tur'],
            'toplam_net': float(toplam_net),
            'dersler': dersler
        }

        conn.close()
        return jsonify(response)

    except Exception as e:
        app.logger.error(f"Deneme detay hatası: {str(e)}", exc_info=True)
        return jsonify({'error': 'Deneme detayları alınamadı', 'details': str(e)}), 500


@app.route('/api/filtrele')
@login_required
def filtrele():
    try:
        tur = request.args.get('tur', '').upper()
        zaman_araligi = request.args.get('zaman_araligi', 'all')
        ders = request.args.get('ders', '')
        ogrenci_uuid = g.user['uuid']  # Kullanıcının uuid'sı

        if zaman_araligi == '3m':
            tarih_filtre = datetime.now() - timedelta(days=90)
        elif zaman_araligi == '6m':
            tarih_filtre = datetime.now() - timedelta(days=180)
        else:
            tarih_filtre = None

        genel_bilgiler = get_genel_bilgiler(tur if tur else None, ogrenci_uuid)
        if tarih_filtre:
            genel_bilgiler = genel_bilgiler[genel_bilgiler['tarih'] >= tarih_filtre]

        if ders:
            filtered_denemeler = []
            for _, deneme in genel_bilgiler.iterrows():
                sonuclar = get_deneme_sonuclari(deneme['uuid'], deneme['tur'], ogrenci_uuid)
                if not sonuclar.empty and ders in sonuclar['ders'].values:
                    filtered_denemeler.append(deneme)
            genel_bilgiler = pd.DataFrame(filtered_denemeler)

        denemeler = []
        for _, deneme in genel_bilgiler.iterrows():
            denemeler.append({
                'uuid': deneme['uuid'],
                'deneme_adi': deneme['deneme_adi'],
                'tarih': deneme['tarih'].isoformat(),
                'tur': deneme['tur']
            })

        return jsonify({
            'denemeler': denemeler,
            'toplam': len(denemeler)
        })

    except Exception as e:
        app.logger.error(f"Filtreleme hatası: {str(e)}", exc_info=True)
        return jsonify({'error': 'Filtreleme sırasında hata', 'details': str(e)}), 500


@app.route('/ders-analizleri')
@login_required
def ders_analizleri():
    import sqlite3

    tur = request.args.get('tur', '').upper()
    if tur not in ['TYT', 'AYT']:
        abort(404, description="Geçersiz tür")

    ogrenci_uuid = g.user['uuid']  # Kullanıcının uuid'sı
    db_path = os.path.join(os.getcwd(), 'veritabani.db')
    genel_bilgiler_tablosu = f"genel_bilgiler_{tur.lower()}"
    tam_sonuc_tablosu = f"tam_sonuc_{tur.lower()}"

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Denemeleri ve sonuçları çek
        cursor.execute(f"SELECT * FROM {genel_bilgiler_tablosu} WHERE ogrenci_uuid = ?", (ogrenci_uuid,))
        denemeler_rows = cursor.fetchall()

        denemeler = []
        for deneme_row in denemeler_rows:
            uuid = deneme_row['uuid']
            deneme_adi = deneme_row['deneme_adi']
            tarih = deneme_row['tarih']

            # Sonuçları çek
            cursor.execute(f"SELECT * FROM {tam_sonuc_tablosu} WHERE uuid = ? AND ogrenci_uuid = ?",
                           (uuid, ogrenci_uuid))
            sonuc_rows = cursor.fetchall()
            detaylar = []
            toplam_net = 0.0
            for row in sonuc_rows:
                detaylar.append({
                    'ders': row['ders'],
                    'dogru': row['dogru'],
                    'yanlis': row['yanlis'],
                    'bos': row['bos'],
                    'net': row['net'],
                })
                toplam_net += row['net']

            denemeler.append({
                'deneme_adi': deneme_adi,
                'tarih': tarih,
                'toplam_net': toplam_net,
                'detaylar': detaylar,
            })

        conn.close()
        denemeler.sort(key=lambda x: x['tarih'])

        return render_template('ders-analizleri.html', tur=tur, analizler=denemeler)
    except Exception as e:
        return render_template('ders-analizleri.html', tur=tur, analizler=[], hata=str(e))


# Uygulama başında veritabanı tablolarını oluştur
from modules.excel_writer import init_db

init_db()
check_and_update_user_table_schema()  # <-- Bunu ekleyin

@app.route('/istatistikler')
@login_required
def istatistikler():
    tur = request.args.get('tur', '').upper()  # 'TYT', 'AYT' veya '' (tümü)
    zaman = request.args.get('zaman', 'all')  # '3m', '6m', 'all'
    ogrenci_uuid = g.user['uuid']

    db_path = os.path.join(os.getcwd(), 'veritabani.db')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Zaman aralığı SQL filtresi
        zaman_sql = ""
        if zaman == '3m':
            zaman_sql = "AND tarih >= DATE('now', '-3 months')"
        elif zaman == '6m':
            zaman_sql = "AND tarih >= DATE('now', '-6 months')"

        toplam_dogru = toplam_yanlis = toplam_bos = toplam_net = 0
        zaman_serisi = []
        ders_istatistikleri = {}

        en_yuksek_net = None
        en_yuksek_deneme_adi = ''
        en_yuksek_tarih = ''

        # Hangi türler için istatistik alınacak?
        turler = []
        if tur in ['TYT', 'AYT']:
            turler = [tur]
        else:
            # Tümü için her iki türü ekle
            turler = ['TYT', 'AYT']

        toplam_deneme = 0

        for t in turler:
            genel_bilgiler_tablosu = f"genel_bilgiler_{t.lower()}"
            tam_sonuc_tablosu = f"tam_sonuc_{t.lower()}"

            cursor.execute(
                f"SELECT * FROM {genel_bilgiler_tablosu} WHERE ogrenci_uuid = ? {zaman_sql} ORDER BY tarih ASC",
                (ogrenci_uuid,)
            )
            denemeler_rows = cursor.fetchall()

            if not denemeler_rows:
                continue

            for deneme_row in denemeler_rows:
                uuid = deneme_row['uuid']
                deneme_adi = deneme_row['deneme_adi']
                tarih = deneme_row['tarih']

                cursor.execute(
                    f"SELECT * FROM {tam_sonuc_tablosu} WHERE uuid = ? AND ogrenci_uuid = ?",
                    (uuid, ogrenci_uuid)
                )
                sonuc_rows = cursor.fetchall()

                deneme_toplam_net = 0
                for row in sonuc_rows:
                    ders = row['ders']
                    dogru = row['dogru']
                    yanlis = row['yanlis']
                    bos = row['bos']
                    net = row['net']

                    toplam_dogru += dogru
                    toplam_yanlis += yanlis
                    toplam_bos += bos
                    deneme_toplam_net += net

                    if ders not in ders_istatistikleri:
                        ders_istatistikleri[ders] = {'net': 0, 'dogru': 0, 'yanlis': 0, 'bos': 0, 'adet': 0}
                    ders_istatistikleri[ders]['net'] += net
                    ders_istatistikleri[ders]['dogru'] += dogru
                    ders_istatistikleri[ders]['yanlis'] += yanlis
                    ders_istatistikleri[ders]['bos'] += bos
                    ders_istatistikleri[ders]['adet'] += 1

                toplam_net += deneme_toplam_net
                zaman_serisi.append({'tarih': tarih, 'net': deneme_toplam_net})

                if en_yuksek_net is None or deneme_toplam_net > en_yuksek_net:
                    en_yuksek_net = deneme_toplam_net
                    en_yuksek_deneme_adi = deneme_adi
                    en_yuksek_tarih = tarih

            toplam_deneme += len(denemeler_rows)

        if toplam_deneme == 0:
            # Hiç deneme yok
            return render_template('istatistikler.html', toplam_istatistik=None, tur=tur)

        ortalama_net = toplam_net / toplam_deneme if toplam_deneme > 0 else 0

        ders_ortalamalari = []
        for ders, stats in ders_istatistikleri.items():
            if ders in ["Fen Bilimleri", "Sosyal Bilimler"]:
                continue
            adet = stats['adet']
            ders_ortalamalari.append({
                "ders": ders,
                "net": stats['net'] / adet if adet > 0 else 0,
                "dogru": stats['dogru'],
                "yanlis": stats['yanlis'],
                "bos": stats['bos'],
            })

        toplam_istatistik = type('Obj', (), {})()
        toplam_istatistik.net = ortalama_net
        toplam_istatistik.dogru = toplam_dogru
        toplam_istatistik.yanlis = toplam_yanlis
        toplam_istatistik.bos = toplam_bos

        en_yuksek = None
        if en_yuksek_net is not None:
            en_yuksek = type('Obj', (), {})()
            en_yuksek.net = en_yuksek_net
            en_yuksek.deneme_adi = en_yuksek_deneme_adi
            en_yuksek.tarih = en_yuksek_tarih

        zaman_serisi = sorted(zaman_serisi, key=lambda x: x['tarih'])

        return render_template(
            'istatistikler.html',
            toplam_istatistik=toplam_istatistik,
            en_yuksek=en_yuksek,
            zaman_serisi=zaman_serisi,
            ders_ortalamalari=ders_ortalamalari,
            dogru=toplam_istatistik.dogru,
            yanlis=toplam_istatistik.yanlis,
            bos=toplam_istatistik.bos,
            tur=tur
        )
    except Exception as e:
        return render_template('istatistikler.html', toplam_istatistik=None, hata=str(e))


def get_db():
    """Veritabanı bağlantısını döndürür"""
    db_path = os.path.join(os.getcwd(), 'veritabani.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.text_factory = lambda x: str(x, 'utf-8', 'replace')
    return conn


# =============================================================================
# VERİTABANI TABLOLARİ
# =============================================================================

def init_koc_sohbet_table():
    """Koç sohbetleri tablosunu oluşturur"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS koc_sohbet
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       user_uuid
                       TEXT
                       NOT
                       NULL,
                       role
                       TEXT
                       NOT
                       NULL,
                       message
                       TEXT
                       NOT
                       NULL,
                       created_at
                       DATETIME
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   """)
    conn.commit()
    conn.close()


def init_koc_notlar_table():
    """Koçun hatırlaması gereken notlar tablosunu oluşturur"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS koc_notlar
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       user_uuid
                       TEXT
                       NOT
                       NULL,
                       note
                       TEXT
                       NOT
                       NULL,
                       created_at
                       DATETIME
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   """)
    conn.commit()
    conn.close()


# Tabloları başlat
init_koc_sohbet_table()
init_koc_notlar_table()


# =============================================================================
# CHAT FONKSİYONLARI
# =============================================================================

def get_chat_history(user_uuid, limit=10):
    """
    Kullanıcının chat geçmişini getirir

    Args:
        user_uuid (str): Kullanıcı UUID'si
        limit (int): Getirilecek mesaj sayısı

    Returns:
        list: Chat ge��mişi (role, content formatında)
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
                   SELECT role, message
                   FROM koc_sohbet
                   WHERE user_uuid = ?
                   ORDER BY created_at DESC, id DESC LIMIT ?
                   """, (user_uuid, limit * 2))

    rows = cursor.fetchall()
    conn.close()

    return [{"role": row["role"], "content": row["message"]} for row in reversed(rows)]


def add_chat_message(user_uuid, role, message):
    """
    Chat mesajını veritabanına kaydet

    Args:
        user_uuid (str): Kullanıcı UUID'si
        role (str): Mesaj rolü ('user' veya 'assistant')
        message (str): Mesaj içeriği
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO koc_sohbet (user_uuid, role, message) VALUES (?, ?, ?)",
        (user_uuid, role, message)
    )
    conn.commit()
    conn.close()


# =============================================================================
# NOT FONKSİYONLARI
# =============================================================================

def add_koc_note(user_uuid, note):
    """
    Koç notunu kaydet

    Args:
        user_uuid (str): Kullanıcı UUID'si
        note (str): Kaydedilecek not
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO koc_notlar (user_uuid, note) VALUES (?, ?)",
        (user_uuid, note)
    )
    conn.commit()
    conn.close()


def get_koc_notes(user_uuid, limit=5):
    """
    Kullanıcının koç notlarını getir

    Args:
        user_uuid (str): Kullanıcı UUID'si
        limit (int): Getirilecek not sayısı

    Returns:
        list: Kullanıcının notları
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
                   SELECT note
                   FROM koc_notlar
                   WHERE user_uuid = ?
                   ORDER BY created_at DESC LIMIT ?
                   """, (user_uuid, limit))

    notes = [row["note"] for row in cursor.fetchall()]
    conn.close()
    return notes


def extract_and_save_notes(text, user_uuid):
    """
    AI yanıtından notları ayıkla ve kaydet

    Args:
        text (str): AI yanıtı
        user_uuid (str): Kullanıcı UUID'si
    """
    notlar = re.findall(r"Koç, bu notu hatırla: (.+?)(?:\n|$)", text)
    for note in notlar:
        add_koc_note(user_uuid, note.strip())


# =============================================================================
# HELPER FONKSİYONLARI
# =============================================================================

def get_deneme_ozeti(user_uuid):
    """
    Kullanıcının deneme özetini getirir

    Args:
        user_uuid (str): Kullanıcı UUID'si

    Returns:
        str: Deneme özeti
    """
    denemeler = get_all_denemeler(user_uuid)  # Dışarıda tanımlı fonksiyon

    if denemeler:
        son_deneme = sorted(denemeler, key=lambda x: x['tarih'], reverse=True)[0]
        return (f"Son denemen: {son_deneme['deneme_adi']} ({son_deneme['tarih']}) - "
                f"Toplam Net: {son_deneme['toplam_net']}. Dersler: " +
                ", ".join([f"{d['ders']}: {d['net']} net" for d in son_deneme['detaylar']]))

    return "Henüz deneme sonucu yok."


def get_not_ozeti(user_uuid):
    """
    Kullanıc��nın not özetini getirir

    Args:
        user_uuid (str): Kullanıcı UUID'si

    Returns:
        str: Not özeti
    """
    notlar = get_koc_notes(user_uuid)
    return "\n".join([f"- {n}" for n in notlar]) if notlar else "Hatırlanacak özel bir not bulunmuyor."


def create_system_prompt(deneme_ozet, not_ozeti):
    """
    Sistem promptunu oluşturur

    Args:
        deneme_ozet (str): Deneme özeti
        not_ozeti (str): Not özeti

    Returns:
        str: Sistem prompt metni
    """
    return f"""Sen bir YKS koçusun.

Görevin, kullanıcının verdiği son mesaja **öncelikli olarak yanıt vermek** ve gerekirse önceki verilerle ilişkilendirmektir.

KURALLAR:
- Deneme özeti ve kullanıcı notları rehberin olacak ama asıl odak **kullanıcının yazdıklarıdır.**
- Konuyla ilgisiz genel tavsiyeler verme.
- Cevapların 3-4 kısa cümle olsun, samimi ve motive edici ol.
- Kullanıcı henüz belirtmediyse, hedef, uyku düzeni gibi konuları doğal sorularla öğrenebilirsin(Bunu yaparken soru yağmuruna tutma yavaş yavaş öğren).
- Kullanıcı meslek veya bölüm belirtmedikçe tahminde bulunma, örneğin 'tıp fakültesi' deme.

📚 SINAV BİLGİLERİ:
- TYT: 120 soru, 165 dakika (Türkçe, Matematik, Sosyal Bilgiler, Fen Bilimleri)
- AYT: 160 soru, 180 dakika (Sayısal, Eşit Ağırlık, Sözel alanlarına göre ders dağılımı)
- 4 yanlış 1 doğruyu götürür. Her test için en az 0.5 net yapılmalı.

📊 Son deneme özeti:
{deneme_ozet}

🧠 Kullanıcı notları:
{not_ozeti}

🔁 NOT KAYDETME:
Kullanıcı bir hedef, alışkanlık veya motivasyon bilgisi verirse, cevabının başına 
'Koç, bu notu hatırla: <not>' ifadesini ekle. 
Bu not, sonraki cevaplarda kullanman için kendi hafızanda saklanacak.

Son olarak: Kullanıcıya birebir ilgi gösteren, ihtiyaçlarına göre yol gösteren ve motive eden bir koç gibi konuş."""


def filter_note_lines(text_chunk):
    """
    Not satırlarını filtreler (stream sırasında notları gizler)

    Args:
        text_chunk (str): Filtrelenecek metin

    Returns:
        str: Filtrelenmiş metin
    """
    lines = text_chunk.split('\n')
    filtered_lines = []
    is_note_line = False

    for line in lines:
        if "Koç, bu notu hatırla:" in line:
            is_note_line = True
        elif is_note_line and line.strip() == "":
            is_note_line = False

        if not is_note_line:
            filtered_lines.append(line)

    return '\n'.join(filtered_lines)


# =============================================================================
# FLASK ROUTE FONKSİYONLARI
# =============================================================================

# Groq API anahtarı
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


@app.route('/api/coach-chat-history', methods=['GET'])
@login_required
def get_coach_chat_history():
    """
    Kullanıcının sohbet geçmişini döndürür

    Returns:
        json: Sohbet geçmişi
    """
    user_uuid = g.user['uuid']
    history = get_chat_history(user_uuid, limit=20)

    # Mesajları çiftler halinde grupla (user-assistant)
    chat_pairs = []
    for i in range(0, len(history), 2):
        if i + 1 < len(history):
            user_msg = history[i] if history[i]['role'] == 'user' else history[i + 1]
            assistant_msg = history[i + 1] if history[i + 1]['role'] == 'assistant' else history[i]

            if user_msg['role'] == 'user' and assistant_msg['role'] == 'assistant':
                chat_pairs.append({
                    'user': user_msg['content'],
                    'coach': assistant_msg['content']
                })

    return jsonify({'history': chat_pairs})


@app.route('/api/coach-chat-stream', methods=['GET', 'POST'])
@login_required
def coach_chat_stream():
    # ... (Önceki kodların aynı kalabilir: mesaj alma, uzunluk kontrolü vb.) ...
    
    if request.method == 'POST':
        user_input = request.json.get('message', '').strip()
    else:
        user_input = request.args.get('message', '').strip()
        
    user_uuid = g.user['uuid']
    
    # Mesajı kaydet
    add_chat_message(user_uuid, "user", user_input)

    # --- YENİ KISIM: Senin prompt fonksiyonlarını kullanıyoruz ---
    deneme_ozet = get_deneme_ozeti(user_uuid)
    not_ozeti = get_not_ozeti(user_uuid)
    
    system_prompt = create_system_prompt(deneme_ozet, not_ozeti)
    
    messages = [{"role": "system", "content": system_prompt}]
    history = get_chat_history(user_uuid, limit=6)
    messages.extend(history)
    messages.append({"role": "user", "content": user_input})

    def event_stream():
        collected = ""
        try:
            client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

            # Model ismini buraya dikkat et
            completion = client.chat.completions.create(
                model="openai/gpt-oss-120b", 
                messages=messages,
                temperature=0.7,
                max_completion_tokens=1024, # Token sayısını artırdım
                top_p=0.95,
                stream=True,
                stop=None,
            )

            for chunk in completion:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    collected += delta
                    # Web arayüzüne parça parça gönder
                    yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"

            # Yanıt bittiğinde notları ayıkla ve kaydet
            if collected:
                extract_and_save_notes(collected, user_uuid)
                # Kullanıcıya not satırlarını göstermemek için temizleyip kaydediyoruz
                clean_msg = filter_note_lines(collected) 
                add_chat_message(user_uuid, "assistant", clean_msg)
                
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return Response(event_stream(), mimetype='text/event-stream')

@app.route('/api/coach-chat-clear', methods=['POST'])
@login_required
@csrf.exempt
def coach_chat_clear():
    """
    Chat geçmişini temizler

    Returns:
        json: Başarı durumu
    """
    user_uuid = g.user['uuid']

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM koc_sohbet WHERE user_uuid = ?", (user_uuid,))
    conn.commit()
    conn.close()

    return jsonify({'success': True})
@app.route('/')
def index():
    if g.user:
        return redirect(url_for('panel'))
    return render_template('index.html')


app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)

# --- Görsel silme kuyruğu ---
delete_queue = {}  # {filepath: timestamp}

def schedule_delete(filepath, delay_sec=600):
    """Görseli silmek için kuyruğa ekler ve thread başlatır."""
    delete_queue[filepath] = time.time() + delay_sec

def delete_expired_files():
    """Kuyruktaki süresi dolan dosyaları siler."""
    while True:
        now = time.time()
        to_delete = [fp for fp, ts in delete_queue.items() if now >= ts]
        for fp in to_delete:
            delete_file_if_exists(fp)
            delete_queue.pop(fp, None)
        time.sleep(30)

# Arka planda silme thread'i başlat
threading.Thread(target=delete_expired_files, daemon=True).start()

@app.route('/api/close-roi', methods=['POST'])
@login_required
def close_roi():
    """Kullanıcı pencereyi kapattığında görseli silmek için çağrılır."""
    image_path = request.json.get('image_path')
    if image_path:
        abs_path = os.path.join(os.getcwd(), image_path.lstrip('/\\'))
        delete_file_if_exists(abs_path)
        delete_queue.pop(abs_path, None)
        return jsonify({'deleted': True})
    return jsonify({'deleted': False})

if __name__ == '__main__':
    app.run(debug=True)