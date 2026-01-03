import sqlite3
from datetime import datetime
import os

DB_PATH = "veritabani.db"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        # ogrenciler tablosu
        c.execute("""
        CREATE TABLE IF NOT EXISTS ogrenciler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE,
            isim TEXT
        )
        """)
        # genel_bilgiler_tyt ve ayt
        for tur in ['tyt', 'ayt']:
            c.execute(f"""
            CREATE TABLE IF NOT EXISTS genel_bilgiler_{tur} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_uuid TEXT,
                uuid TEXT,
                deneme_id TEXT,
                deneme_adi TEXT,
                tarih TEXT,
                tur TEXT
            )
            """)
            c.execute(f"""
            CREATE TABLE IF NOT EXISTS cevaplar_{tur} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_uuid TEXT,
                uuid TEXT,
                ders TEXT,
                soru_no INTEGER,
                dogru_cevap TEXT,
                ogrenci_cevap TEXT
            )
            """)
            c.execute(f"""
            CREATE TABLE IF NOT EXISTS tam_sonuc_{tur} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_uuid TEXT,
                uuid TEXT,
                ders TEXT,
                dogru INTEGER,
                yanlis INTEGER,
                bos INTEGER,
                net REAL,
                toplam INTEGER,
                tarih TEXT
            )
            """)
        conn.commit()


def get_db_connection():
    dir_name = os.path.dirname(DB_PATH)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def write_ogrenci(isim, uuid):
    """
    Yeni öğrenci ekler veya var olanı günceller.
    """
    with get_db_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO ogrenciler (uuid, isim) VALUES (?, ?)
        """, (uuid, isim))
        conn.commit()
    return True


def write_genel_bilgiler(ogrenci_uuid, deneme_uuid, deneme_id, deneme_adi, tarih, tur):
    """
    genel_bilgiler_ayt/tyt tablosuna kayıt ekler.
    """
    table = f"genel_bilgiler_{tur.lower()}"
    with get_db_connection() as conn:
        conn.execute(f"""
            INSERT OR REPLACE INTO {table}
            (ogrenci_uuid, uuid, deneme_id, deneme_adi, tarih, tur)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ogrenci_uuid, deneme_uuid, deneme_id, deneme_adi, tarih, tur.upper()))
        conn.commit()
    return True


def write_cevaplar(ogrenci_uuid, deneme_uuid, cevap_anahtari, ogrenci_cevaplari, tur):
    """
    cevaplar_ayt/tyt tablosuna kayıt ekler.
    """
    table = f"cevaplar_{tur.lower()}"
    with get_db_connection() as conn:
        for ders in cevap_anahtari:
            anahtarlar = cevap_anahtari[ders]
            ogr_cevaplar = ogrenci_cevaplari.get(ders, [])
            soru_sayisi = min(len(anahtarlar), len(ogr_cevaplar))
            for i in range(soru_sayisi):
                dogru = anahtarlar[i]
                ogr_cevap = ogr_cevaplar[i]
                conn.execute(f"""
                    INSERT INTO {table}
                    (ogrenci_uuid, uuid, ders, soru_no, dogru_cevap, ogrenci_cevap)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ogrenci_uuid, deneme_uuid, ders, i+1, dogru, ogr_cevap))
        conn.commit()
    return True


def write_sonuclar(ogrenci_uuid, deneme_uuid, sonuc, tur):
    """
    tam_sonuc_ayt/tyt tablosuna kayıt ekler.
    """
    table = f"tam_sonuc_{tur.lower()}"
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with get_db_connection() as conn:
        for ders, degerler in sonuc.items():
            if ders == "Toplam":
                continue
            conn.execute(f"""
                INSERT INTO {table}
                (ogrenci_uuid, uuid, ders, dogru, yanlis, bos, net, toplam, tarih)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ogrenci_uuid,
                deneme_uuid,
                ders,
                int(degerler.get('dogru', 0)) if degerler.get('dogru') is not None else 0,
                int(degerler.get('yanlis', 0)) if degerler.get('yanlis') is not None else 0,
                int(degerler.get('bos', 0)) if degerler.get('bos') is not None else 0,
                float(degerler.get('net', 0.0)) if degerler.get('net') is not None else 0.0,
                int(degerler.get('toplam', 0)) if degerler.get('toplam') is not None else 0,
                now
            ))
        conn.commit()
    return True

# Modül yüklendiğinde veritabanı tabloları oluşturulsun
init_db()
