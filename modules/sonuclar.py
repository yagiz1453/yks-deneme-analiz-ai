# modules/sonuclar.py

import sqlite3
import pandas as pd
from datetime import datetime
from collections import defaultdict

DB_PATH = "veritabani.db"

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def temizle_ders_adi(ders):
    # TYT_Türkçe → Türkçe, AYT_Coğrafya → Coğrafya
    return ders.replace("TYT_", "").replace("AYT_", "").strip()

def oku_veriler(tur, ogrenci_uuid=None):
    """
    Veritabanından genel_bilgiler ve tam_sonuc tablolarını okur.
    """
    gb_table = f"genel_bilgiler_{tur.lower()}"
    ts_table = f"tam_sonuc_{tur.lower()}"
    with get_db_connection() as conn:
        if ogrenci_uuid:
            gb_df = pd.read_sql_query(f"SELECT * FROM {gb_table} WHERE ogrenci_uuid = ?", conn, params=(ogrenci_uuid,))
            ts_df = pd.read_sql_query(f"SELECT * FROM {ts_table} WHERE ogrenci_uuid = ?", conn, params=(ogrenci_uuid,))
        else:
            gb_df = pd.read_sql_query(f"SELECT * FROM {gb_table}", conn)
            ts_df = pd.read_sql_query(f"SELECT * FROM {ts_table}", conn)
    # --- TYT için Sosyal Bilimler ve Fen Bilimleri'nde sadece 1-20 arası sorular kalsın ---
    if tur.lower() == "tyt" and not ts_df.empty:
        mask = ~(
            ((ts_df['ders'].str.lower() == 'sosyal bilimler') | (ts_df['ders'].str.lower() == 'fen bilimleri'))
            & (ts_df['toplam'] > 20)
        )
        ts_df = ts_df[mask]
    return gb_df, ts_df

def hesapla_istatistikler(tur=None, zaman_araligi="all", ogrenci_uuid=None):
    genel_bilgi_df, sonuc_df = pd.DataFrame(), pd.DataFrame()

    for t in ['tyt', 'ayt']:
        if tur and tur.lower() != t:
            continue
        gb, ts = oku_veriler(t, ogrenci_uuid)
        genel_bilgi_df = pd.concat([genel_bilgi_df, gb])
        sonuc_df = pd.concat([sonuc_df, ts])

    if genel_bilgi_df.empty or sonuc_df.empty:
        return {"error": "Veri bulunamadı"}

    genel_bilgi_df['tarih'] = pd.to_datetime(genel_bilgi_df['tarih'])
    sonuc_df['tarih'] = pd.to_datetime(sonuc_df['tarih'])

    if zaman_araligi in ["3m", "6m"]:
        ay = int(zaman_araligi.replace("m", ""))
        baslangic = pd.Timestamp.today() - pd.DateOffset(months=ay)
        genel_bilgi_df = genel_bilgi_df[genel_bilgi_df['tarih'] >= baslangic]

    genel_kartlar = {
        "toplam_deneme": len(genel_bilgi_df),
        "en_yuksek_net": {"net": None, "deneme_adi": None, "tarih": None},
        "son_deneme": {"toplam_net": None, "deneme_adi": None, "tarih": None}
    }

    netler = []
    for _, row in genel_bilgi_df.iterrows():
        deneme_uuid = row['uuid']
        df = sonuc_df[sonuc_df['uuid'] == deneme_uuid]
        toplam_net = df['net'].sum()
        netler.append({
            "uuid": deneme_uuid,
            "toplam_net": toplam_net,
            "deneme_adi": row['deneme_adi'],
            "tarih": row['tarih'],
            "tur": row['tur'].upper()
        })

    if netler:
        en_yuksek = max(netler, key=lambda x: x['toplam_net'])
        son_deneme = sorted(netler, key=lambda x: x['tarih'])[-1]
        genel_kartlar["en_yuksek_net"] = {
            "net": round(en_yuksek["toplam_net"], 2),
            "deneme_adi": en_yuksek["deneme_adi"],
            "tarih": pd.to_datetime(en_yuksek["tarih"]).strftime("%Y-%m-%d")
        }
        genel_kartlar["son_deneme"] = {
            "toplam_net": round(son_deneme["toplam_net"], 2),
            "deneme_adi": son_deneme["deneme_adi"],
            "tarih": pd.to_datetime(son_deneme["tarih"]).strftime("%Y-%m-%d")
        }

    son_denemeler = sorted(netler, key=lambda x: x['tarih'], reverse=True)[:5]

    zaman_serisi = {
        "labels": [pd.to_datetime(n["tarih"]).strftime("%Y-%m-%d") for n in netler]
    }
    if tur:
        zaman_serisi[tur.lower()] = [round(n["toplam_net"], 2) for n in netler]
    else:
        zaman_serisi["tyt"] = [round(n["toplam_net"], 2) for n in netler if n["tur"] == "TYT"]
        zaman_serisi["ayt"] = [round(n["toplam_net"], 2) for n in netler if n["tur"] == "AYT"]

    ders_istatistikleri = {}
    for _, row in sonuc_df.iterrows():
        ders = temizle_ders_adi(row["ders"])
        if ders not in ders_istatistikleri:
            ders_istatistikleri[ders] = {"dogru": 0, "yanlis": 0, "bos": 0, "net": 0.0}
        ders_istatistikleri[ders]["dogru"] += int(row["dogru"])
        ders_istatistikleri[ders]["yanlis"] += int(row["yanlis"])
        ders_istatistikleri[ders]["bos"] += int(row["bos"])
        ders_istatistikleri[ders]["net"] += float(row["net"])

    for d in ders_istatistikleri:
        ders_istatistikleri[d]["net"] = round(ders_istatistikleri[d]["net"], 2)

    cevaplama_istatistikleri = {
        "dogru": int(sonuc_df['dogru'].sum()),
        "yanlis": int(sonuc_df['yanlis'].sum()),
        "bos": int(sonuc_df['bos'].sum()),
        "toplam_soru": int(sonuc_df[['dogru', 'yanlis', 'bos']].sum().sum())
    }

    return {
        "genel_kartlar": genel_kartlar,
        "son_denemeler": son_denemeler,
        "zaman_serisi": zaman_serisi,
        "ders_istatistikleri": ders_istatistikleri,
        "cevaplama_istatistikleri": cevaplama_istatistikleri
    }

def get_all_denemeler(ogrenci_uuid=None):
    denemeler = []
    for tur in ['tyt', 'ayt']:
        gb_df, sonuc_df = oku_veriler(tur, ogrenci_uuid)
        if gb_df.empty or sonuc_df.empty:
            continue
        gb_df['tarih'] = pd.to_datetime(gb_df['tarih'])
        sonuc_df['tarih'] = pd.to_datetime(sonuc_df['tarih'])

        for _, row in gb_df.iterrows():
            deneme_uuid = row['uuid']
            df = sonuc_df[sonuc_df['uuid'] == deneme_uuid]
            if df.empty:
                continue

            toplam_net = df['net'].sum()
            dogru = df['dogru'].sum()
            yanlis = df['yanlis'].sum()
            bos = df['bos'].sum()

            # Ana dersleri hariç tut (ör: Fen Bilimleri, Sosyal Bilimler)
            ana_dersler = ['Fen Bilimleri', 'Sosyal Bilimler']
            detaylar = []
            for ders, ders_df in df.groupby("ders"):
                temiz_ders = temizle_ders_adi(ders)
                if temiz_ders in ana_dersler:
                    continue  # Ana dersleri atla
                detaylar.append({
                    "ders": temiz_ders,
                    "dogru": int(ders_df["dogru"].sum()),
                    "yanlis": int(ders_df["yanlis"].sum()),
                    "bos": int(ders_df["bos"].sum()),
                    "net": round(ders_df["net"].sum(), 2)
                })

            denemeler.append({
                "uuid": deneme_uuid,
                "deneme_adi": row["deneme_adi"],
                "tarih": pd.to_datetime(row["tarih"]).strftime("%Y-%m-%d"),
                "tur": row["tur"].upper(),
                "toplam_dogru": int(dogru),
                "toplam_yanlis": int(yanlis),
                "toplam_bos": int(bos),
                "toplam_net": round(toplam_net, 2),
                "ders_detaylari": {d["ders"]: d for d in detaylar},
                "detaylar": detaylar  # <-- analizler.html için
            })

    return denemeler

def get_denemeler_by_tur(tur, ogrenci_uuid=None):
    return [d for d in get_all_denemeler(ogrenci_uuid) if d.get("tur") == tur.upper()]
