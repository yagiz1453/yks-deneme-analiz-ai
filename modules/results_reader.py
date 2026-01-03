import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

DB_PATH = "veritabani.db"


def get_db_connection():
    return sqlite3.connect(DB_PATH)


# Global değişkenler - otomatik Excel yazma kontrolü için
_last_processed_uuid = None
_last_processed_tur = None


def alt_dersi_belirle(tur: str, ders: str, soru_no: int) -> str:
    ders = ders.strip().lower()
    ders_normalizer = {
        'sosyal bil.': 'sosyal bilimler',
        'sosyal bilgiler': 'sosyal bilimler',
        'sosyal': 'sosyal bilimler',
        'fen bil.': 'fen bilimleri',
        'fen': 'fen bilimleri',
        'temel matematik': 'matematik',
        'türk dili': 'türkçe',
        'edebiyat': 'türkçe'
    }
    ders = ders_normalizer.get(ders, ders)

    if tur.lower() == 'tyt':
        if ders == 'sosyal bilimler':
            if 1 <= soru_no <= 5:
                return 'Tarih'
            elif 6 <= soru_no <= 10:
                return 'Coğrafya'
            elif 11 <= soru_no <= 15:
                return 'Felsefe'
            elif 16 <= soru_no <= 20:
                return 'Din Kültürü ve Ahlak Bilgisi'
            else:
                return None
        elif ders == 'fen bilimleri':
            if 1 <= soru_no <= 7:
                return 'Fizik'
            elif 8 <= soru_no <= 14:
                return 'Kimya'
            elif 15 <= soru_no <= 20:
                return 'Biyoloji'
            else:
                return None
        elif ders in ['matematik', 'geometri']:
            return 'Matematik'
        elif ders == 'türkçe':
            return 'Türkçe'
    elif tur.lower() == 'ayt':
        if ders == 'matematik':
            if 1 <= soru_no <= 20:
                return 'Temel Matematik'
            elif 21 <= soru_no <= 40:
                return 'Geometri'
        elif ders == 'sosyal bilimler':
            if 1 <= soru_no <= 10:
                return 'Tarih'
            elif 11 <= soru_no <= 20:
                return 'Coğrafya'
            elif 21 <= soru_no <= 30:
                return 'Felsefe'
            elif 31 <= soru_no <= 40:
                return 'Din Kültürü'
        elif ders == 'fen bilimleri':
            if 1 <= soru_no <= 14:
                return 'Fizik'
            elif 15 <= soru_no <= 28:
                return 'Kimya'
            elif 29 <= soru_no <= 42:
                return 'Biyoloji'
        elif ders == 'türkçe':
            return 'Türkçe'
        else:
            return ders.title()

    return ders.title()


def hesapla_sonuclar(tur: str, uuid: str, ogrenci_uuid: str):
    tur = tur.lower()
    table = f"cevaplar_{tur}"
    with get_db_connection() as conn:
        df_deneme = pd.read_sql_query(
            f"SELECT * FROM {table} WHERE uuid = ? AND ogrenci_uuid = ?",
            conn, params=(uuid, ogrenci_uuid)
        )
    if df_deneme.empty:
        raise ValueError(f"{uuid} ID'li deneme {tur.upper()} türünde boş!")

    sonuc_tablosu = {}

    if tur == "tyt":
        ana_dersler = [
            'Türkçe',
            'Matematik',
            'Fen Bilimleri',
            'Sosyal Bilimler'
        ]
        alt_dersler = [
            'Tarih', 'Coğrafya', 'Felsefe', 'Din Kültürü ve Ahlak Bilgisi',
            'Fizik', 'Kimya', 'Biyoloji'
        ]
    else:
        ana_dersler = []
        alt_dersler = []

    # Ana dersler ve alt dersler için sıfırla
    for ders in ana_dersler + alt_dersler:
        sonuc_tablosu[ders] = {'dogru': 0, 'yanlis': 0, 'bos': 0, 'net': 0.0}

    # Her satırı işle
    for _, row in df_deneme.iterrows():
        ders = str(row['ders']).strip()
        soru_no = int(row['soru_no'])
        dogru_cevap = str(row['dogru_cevap']).strip().upper() if pd.notna(row['dogru_cevap']) else ''
        ogrenci_cevap = str(row['ogrenci_cevap']).strip().upper() if pd.notna(row['ogrenci_cevap']) else ''

        if dogru_cevap in ['NAN', 'NONE', '']:
            dogru_cevap = ''
        if ogrenci_cevap in ['NAN', 'NONE', '']:
            ogrenci_cevap = ''

        # Ana dersler
        if ders in sonuc_tablosu:
            if ogrenci_cevap == '':
                sonuc_tablosu[ders]['bos'] += 1
            elif ogrenci_cevap == dogru_cevap and dogru_cevap != '':
                sonuc_tablosu[ders]['dogru'] += 1
            else:
                sonuc_tablosu[ders]['yanlis'] += 1

        # Alt dersler (sadece TYT için)
        if tur == "tyt":
            alt_ders = alt_dersi_belirle(tur, ders, soru_no)
            if alt_ders and alt_ders in sonuc_tablosu:
                if ogrenci_cevap == '':
                    sonuc_tablosu[alt_ders]['bos'] += 1
                elif ogrenci_cevap == dogru_cevap and dogru_cevap != '':
                    sonuc_tablosu[alt_ders]['dogru'] += 1
                else:
                    sonuc_tablosu[alt_ders]['yanlis'] += 1

    # Netleri hesapla
    for ders, sonuc in sonuc_tablosu.items():
        net = sonuc['dogru'] - (sonuc['yanlis'] / 4.0)
        sonuc['net'] = round(net, 2)
        sonuc['toplam'] = sonuc['dogru'] + sonuc['yanlis'] + sonuc['bos']

    # Ana derslerin netini alt derslerden topla (sosyal/fen)
    if tur == 'tyt':
        # Sosyal Bilimler
        for ana, alts in [
            ('Sosyal Bilimler', ['Tarih', 'Coğrafya', 'Felsefe', 'Din Kültürü ve Ahlak Bilgisi']),
            ('Fen Bilimleri', ['Fizik', 'Kimya', 'Biyoloji'])
        ]:
            toplam_dogru = toplam_yanlis = toplam_bos = toplam_net = toplam_toplam = 0
            for alt in alts:
                toplam_dogru += sonuc_tablosu[alt]['dogru']
                toplam_yanlis += sonuc_tablosu[alt]['yanlis']
                toplam_bos += sonuc_tablosu[alt]['bos']
                toplam_net += sonuc_tablosu[alt]['net']
                toplam_toplam += sonuc_tablosu[alt]['toplam']
            sonuc_tablosu[ana]['dogru'] = toplam_dogru
            sonuc_tablosu[ana]['yanlis'] = toplam_yanlis
            sonuc_tablosu[ana]['bos'] = toplam_bos
            sonuc_tablosu[ana]['net'] = round(toplam_net, 2)
            sonuc_tablosu[ana]['toplam'] = toplam_toplam

    # Ders adlarına TYT_/AYT_ ön eki ekle
    prefix = tur.upper() + "_"
    sonuc_tablosu_prefixed = {}
    for ders_adi, veri in sonuc_tablosu.items():
        yeni_ad = f"{prefix}{ders_adi}"
        sonuc_tablosu_prefixed[yeni_ad] = veri

    return sonuc_tablosu_prefixed


def get_genel_bilgiler(tur=None):
    dfs = []
    for t in ['tyt', 'ayt']:
        if tur and t != tur.lower():
            continue
        table = f"genel_bilgiler_{t}"
        with get_db_connection() as conn:
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        if not df.empty:
            dfs.append(df)
    if not dfs:
        return pd.DataFrame()
    combined = pd.concat(dfs, ignore_index=True)
    combined['tarih'] = pd.to_datetime(combined['tarih'])
    return convert_types(combined.sort_values('tarih', ascending=False))


def get_son_denemeler(limit=5):
    df = get_genel_bilgiler()
    if df.empty:
        return []
    return convert_types(df.head(limit)).to_dict('records')


def get_deneme_sonuclari(deneme_uuid, tur, ogrenci_uuid):
    table = f"tam_sonuc_{tur.lower()}"
    with get_db_connection() as conn:
        df = pd.read_sql_query(
            f"SELECT * FROM {table} WHERE uuid = ? AND ogrenci_uuid = ?",
            conn, params=(deneme_uuid, ogrenci_uuid)
        )
    return convert_types(df)


def get_ders_istatistikleri(tur=None, ogrenci_uuid=None):
    try:
        genel_bilgiler = get_genel_bilgiler(tur)
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
    try:
        df = get_genel_bilgiler(tur)
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
    try:
        genel_bilgiler = get_genel_bilgiler(tur)
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
                cevaplar = pd.read_sql_query(
                    f"SELECT * FROM {table} WHERE uuid = ? AND ogrenci_uuid = ?",
                    conn, params=(deneme['uuid'], ogrenci_uuid)
                )
            if cevaplar.empty:
                continue
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
    try:
        genel_bilgiler = get_genel_bilgiler(tur)
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


def convert_types(df):
    if df.empty:
        return df
    for col in df.select_dtypes(include=[np.int64]).columns:
        df[col] = df[col].astype(int)
    for col in df.select_dtypes(include=[np.float64]).columns:
        df[col] = df[col].astype(float)
    return df


def get_ders_siralamasi(tur: str):
    """
    Belirtilen tür için ders sıralamasını döndürür.
    """
    if tur.lower() == 'tyt':
        return {
            'ana_dersler': ['Türkçe', 'Matematik'],
            'alt_dersler': {
                'Sosyal Bilimler': ['Tarih', 'Coğrafya', 'Felsefe', 'Din Kültürü'],
                'Fen Bilimleri': ['Fizik', 'Kimya', 'Biyoloji']
            }
        }
    elif tur.lower() == 'ayt':
        return {
            'bolumler': {
                'Sayısal': ['Temel Matematik', 'Geometri', 'Fizik', 'Kimya', 'Biyoloji'],
                'Eşit Ağırlık': ['Türkçe', 'Tarih', 'Coğrafya', 'Felsefe', 'Din Kültürü', 'Temel Matematik',
                                 'Geometri'],
                'Sözel': ['Türkçe', 'Tarih', 'Coğrafya', 'Felsefe', 'Din Kültürü']
            }
        }
    return {}


# Modül çağrıldığında otomatik çalışacak ana fonksiyon
def process_deneme_results(uuid: str, tur: str, ogrenci_uuid: str):
    """
    Ana işlem fonksiyonu - modül çağrıldığında bu fonksiyon kullanılır.

    Args:
        uuid (str): Deneme UUID'si
        tur (str): Deneme türü ('tyt' veya 'ayt')

    Returns:
        dict: İşlem sonucu ve sonuçlar
    """
    try:
        # Sonuçları hesapla
        sonuclar = hesapla_sonuclar(tur, uuid, ogrenci_uuid)

        # Sonuçları veritabanına yazmak için başka bir modül kullanılmalı
        return {
            'success': True,
            'message': f"{uuid} ID'li {tur.upper()} deneme sonuçları başarıyla işlendi.",
            'sonuclar': sonuclar
        }

    except Exception as e:
        return {
            'success': False,
            'message': f"İşlem sırasında hata oluştu: {str(e)}",
            'sonuclar': None
        }


# Geriye uyumluluk için eski fonksiyon adlarını koruyalım
def calculate_and_save_results(uuid: str, tur: str, ogrenci_uuid: str):
    """Geriye uyumluluk için alternatif fonksiyon adı"""
    return process_deneme_results(uuid, tur, ogrenci_uuid)
