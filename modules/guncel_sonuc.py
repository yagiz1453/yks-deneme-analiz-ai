import os
import pandas as pd
import sqlite3
from datetime import datetime

DB_PATH = "veritabani.db"

def guncel_sonuclar_dosyasi_guncelle(tur: str, uuid: str, ogrenci_uuid: str, deneme_sonuclari: dict):
    """
    Deneme sonuçlarını tam_sonuc_<tur> tablosuna kaydeder veya günceller.

    Args:
        tur (str): 'tyt' veya 'ayt' (küçük harf).
        uuid (str): Deneme kimliği.
        ogrenci_uuid (str): Öğrenci uuid.
        deneme_sonuclari (dict): Ders bazında sonuç bilgileri, örneğin:
            {
                'Matematik': {'dogru': 15, 'yanlis': 5, 'bos': 0, 'net': 13.75, 'toplam': 20},
                ...
            }
    """
    table = f"tam_sonuc_{tur.lower()}"
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect(DB_PATH) as conn:
        for ders, detay in deneme_sonuclari.items():
            # Önce varsa eski kaydı sil
            conn.execute(
                f"DELETE FROM {table} WHERE uuid = ? AND ders = ? AND ogrenci_uuid = ?",
                (uuid, ders, ogrenci_uuid)
            )
            conn.execute(
                f"""INSERT INTO {table}
                (ogrenci_uuid, uuid, ders, dogru, yanlis, bos, net, toplam, tarih)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ogrenci_uuid,
                    uuid,
                    ders,
                    int(detay.get('dogru', 0)) if detay.get('dogru') is not None else 0,
                    int(detay.get('yanlis', 0)) if detay.get('yanlis') is not None else 0,
                    int(detay.get('bos', 0)) if detay.get('bos') is not None else 0,
                    float(detay.get('net', 0.0)) if detay.get('net') is not None else 0.0,
                    int(detay.get('toplam', 0)) if detay.get('toplam') is not None else 0,
                    now
                )
            )
        conn.commit()
