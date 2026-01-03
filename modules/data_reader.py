import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from collections import defaultdict

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


# Modül yüklendiğinde veritabanı tabloları oluşturulsun
init_db()


def get_db_connection():
    return sqlite3.connect(DB_PATH)


def convert_types(df):
    """DataFrame'deki numpy veri tiplerini Python temel tiplerine dönüştür"""
    if df.empty:
        return df

    for col in df.select_dtypes(include=[np.int64]).columns:
        df[col] = df[col].astype(int)
    for col in df.select_dtypes(include=[np.float64]).columns:
        df[col] = df[col].astype(float)
    return df


def get_genel_bilgiler(tur=None, ogrenci_uuid=None):
    """Tüm deneme bilgilerini getirir (veritabanından)"""
    dfs = []
    for t in ['tyt', 'ayt']:
        if tur and t != tur.lower():
            continue
        table = f"genel_bilgiler_{t}"
        with get_db_connection() as conn:
            if ogrenci_uuid:
                df = pd.read_sql_query(f"SELECT * FROM {table} WHERE ogrenci_uuid = ?", conn, params=(ogrenci_uuid,))
            else:
                df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        if not df.empty:
            dfs.append(df)
    if not dfs:
        return pd.DataFrame()
    combined = pd.concat(dfs, ignore_index=True)
    combined['tarih'] = pd.to_datetime(combined['tarih'])
    return convert_types(combined.sort_values('tarih', ascending=False))


def get_son_denemeler(limit=5, ogrenci_uuid=None):
    """Son denemeleri getirir"""
    df = get_genel_bilgiler(ogrenci_uuid=ogrenci_uuid)
    if df.empty:
        return []

    return convert_types(df.head(limit)).to_dict('records')


def get_deneme_sonuclari(deneme_uuid, tur, ogrenci_uuid=None):
    """Belirli bir denemenin sonuçlarını getirir (veritabanından)"""
    table = f"tam_sonuc_{tur.lower()}"
    with get_db_connection() as conn:
        if ogrenci_uuid:
            df = pd.read_sql_query(
                f"SELECT * FROM {table} WHERE uuid = ? AND ogrenci_uuid = ?",
                conn, params=(deneme_uuid, ogrenci_uuid)
            )
        else:
            df = pd.read_sql_query(
                f"SELECT * FROM {table} WHERE uuid = ?",
                conn, params=(deneme_uuid,)
            )
    # --- TYT için Sosyal Bilimler ve Fen Bilimleri'nde sadece 1-20 arası sorular kalsın ---
    if tur.lower() == "tyt" and not df.empty:
        mask = ~(
            ((df['ders'].str.lower() == 'sosyal bilimler') | (df['ders'].str.lower() == 'fen bilimleri'))
            & (df['toplam'] > 20)
        )
        df = df[mask]
    return convert_types(df)


def get_ders_istatistikleri(tur=None, ogrenci_uuid=None):
    """Ders bazlı istatistikleri hesaplar"""
    try:
        genel_bilgiler = get_genel_bilgiler(tur, ogrenci_uuid)
        if genel_bilgiler.empty:
            return {}

        three_months_ago = datetime.now() - timedelta(days=90)
        recent_denemeler = genel_bilgiler[genel_bilgiler['tarih'] >= three_months_ago]
        if recent_denemeler.empty:
            return {}

        istatistikler = defaultdict(lambda: {'net': 0, 'dogru': 0, 'yanlis': 0, 'bos': 0, 'count': 0})

        for _, deneme in recent_denemeler.iterrows():
            sonuclar = get_deneme_sonuclari(deneme['uuid'], deneme['tur'], ogrenci_uuid)
            if sonuclar.empty:
                continue

            for _, ders_sonuc in sonuclar.iterrows():
                ders = ders_sonuc['ders']
                istatistikler[ders]['net'] += ders_sonuc.get('net', 0)
                istatistikler[ders]['dogru'] += ders_sonuc.get('dogru', 0)
                istatistikler[ders]['yanlis'] += ders_sonuc.get('yanlis', 0)
                istatistikler[ders]['bos'] += ders_sonuc.get('bos', 0)
                istatistikler[ders]['count'] += 1

        # Ortalamaları hesapla ve formatla
        result = {}
        for ders, veri in istatistikler.items():
            if veri['count'] > 0:
                result[ders] = {
                    'net': round(float(veri['net'] / veri['count']), 2),
                    'dogru': round(float(veri['dogru'] / veri['count']), 1),
                    'yanlis': round(float(veri['yanlis'] / veri['count']), 1),
                    'bos': round(float(veri['bos'] / veri['count']), 1)
                }

        return result

    except Exception as e:
        print(f"Ders istatistikleri hesaplanırken hata: {str(e)}")
        return {}


def get_zaman_serisi(tur=None, ogrenci_uuid=None):
    """Zamana göre net değişimini getirir"""
    try:
        df = get_genel_bilgiler(tur, ogrenci_uuid)
        if df.empty:
            return {'labels': [], 'tyt': [], 'ayt': []}

        df['ay'] = df['tarih'].dt.to_period('M')
        grouped = df.groupby('ay')

        zaman_serisi = {'labels': [], 'tyt': [], 'ayt': []}

        for ay, group in grouped:
            zaman_serisi['labels'].append(ay.strftime('%B %Y'))

            tyt_toplam = 0
            ayt_toplam = 0
            count_tyt = 0
            count_ayt = 0

            for _, deneme in group.iterrows():
                sonuclar = get_deneme_sonuclari(deneme['uuid'], deneme['tur'], ogrenci_uuid)
                if sonuclar.empty:
                    continue

                toplam_net = sonuclar['net'].sum()

                if deneme['tur'].lower() == 'tyt':
                    tyt_toplam += toplam_net
                    count_tyt += 1
                else:
                    ayt_toplam += toplam_net
                    count_ayt += 1

            zaman_serisi['tyt'].append(round(float(tyt_toplam / count_tyt), 1) if count_tyt > 0 else 0)
            if not tur:
                zaman_serisi['ayt'].append(round(float(ayt_toplam / count_ayt), 1) if count_ayt > 0 else 0)

        return zaman_serisi
    except Exception as e:
        print(f"Zaman serisi oluşturulurken hata: {str(e)}")
        return {'labels': [], 'tyt': [], 'ayt': []}


def get_cevaplama_istatistikleri(tur=None, ogrenci_uuid=None):
    """Genel cevaplama istatistiklerini getirir (veritabanından)"""
    try:
        genel_bilgiler = get_genel_bilgiler(tur, ogrenci_uuid)
        if genel_bilgiler.empty:
            return {'toplam_soru': 0, 'dogru': 0, 'yanlis': 0, 'bos': 0, 'ders_dagilim': {}}

        istatistikler = {
            'toplam_soru': 0,
            'dogru': 0,
            'yanlis': 0,
            'bos': 0,
            'ders_dagilim': defaultdict(int)
        }

        for _, deneme in genel_bilgiler.iterrows():
            table = f"cevaplar_{deneme['tur'].lower()}"
            with get_db_connection() as conn:
                if ogrenci_uuid:
                    cevaplar = pd.read_sql_query(
                        f"SELECT * FROM {table} WHERE uuid = ? AND ogrenci_uuid = ?",
                        conn, params=(deneme['uuid'], ogrenci_uuid)
                    )
                else:
                    cevaplar = pd.read_sql_query(
                        f"SELECT * FROM {table} WHERE uuid = ?",
                        conn, params=(deneme['uuid'],)
                    )
            if cevaplar.empty:
                continue

            # --- YALNIZCA GEÇERLİ SORULARI DAHİL ET ---
            if deneme['tur'].lower() == 'tyt':
                # Sosyal Bilimler ve Fen Bilimleri için sadece 1-20 arası sorular
                mask = ~(
                    ((cevaplar['ders'].str.lower() == 'sosyal bilimler') | (cevaplar['ders'].str.lower() == 'fen bilimleri'))
                    & (cevaplar['soru_no'] > 20)
                )
                cevaplar = cevaplar[mask]

            istatistikler['toplam_soru'] += len(cevaplar)
            istatistikler['dogru'] += (cevaplar['dogru_cevap'] == cevaplar['ogrenci_cevap']).sum()
            istatistikler['yanlis'] += ((cevaplar['dogru_cevap'] != cevaplar['ogrenci_cevap']) &
                                        (cevaplar['ogrenci_cevap'].notna())).sum()
            istatistikler['bos'] += (cevaplar['ogrenci_cevap'].isna()).sum()

            for ders, count in cevaplar['ders'].value_counts().items():
                istatistikler['ders_dagilim'][ders] += count

        istatistikler['dogru'] = int(istatistikler['dogru'])
        istatistikler['yanlis'] = int(istatistikler['yanlis'])
        istatistikler['bos'] = int(istatistikler['bos'])
        istatistikler['ders_dagilim'] = dict(istatistikler['ders_dagilim'])

        return istatistikler
    except Exception as e:
        print(f"Cevaplama istatistikleri hesaplanırken hata: {str(e)}")
        return {'toplam_soru': 0, 'dogru': 0, 'yanlis': 0, 'bos': 0, 'ders_dagilim': {}}


def get_en_yuksek_net(tur=None, ogrenci_uuid=None):
    """Belirtilen türdeki en yüksek neti ve deneme bilgilerini getirir"""
    try:
        genel_bilgiler = get_genel_bilgiler(tur, ogrenci_uuid)
        if genel_bilgiler.empty:
            return None

        en_yuksek_net = 0
        en_yuksek_bilgi = None

        for _, deneme in genel_bilgiler.iterrows():
            sonuclar = get_deneme_sonuclari(deneme['uuid'], deneme['tur'], ogrenci_uuid)
            if sonuclar.empty:
                continue

            toplam_net = sonuclar['net'].sum()
            if toplam_net > en_yuksek_net:
                en_yuksek_net = toplam_net
                en_yuksek_bilgi = {
                    'net': round(float(toplam_net), 2),
                    'deneme_adi': deneme['deneme_adi'],
                    'tarih': deneme['tarih'].strftime('%Y-%m-%d') if isinstance(deneme['tarih'], pd.Timestamp) else
                    deneme['tarih'],
                    'tur': deneme['tur']
                }

        return en_yuksek_bilgi
    except Exception as e:
        print(f"En yüksek net bulunurken hata: {str(e)}")
        return None