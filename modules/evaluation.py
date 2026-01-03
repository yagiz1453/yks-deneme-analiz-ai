def hesapla_sonuc(cevap_anahtari, ogrenci_cevaplari, tur='TYT'):
    tur = tur.upper()
    sonuc = {}

    if tur == 'TYT':
        # Soru dağılımı
        tyt_dersler = {
            'Türkçe': (0, 40),
            'Matematik': (0, 40),
            'Fen Bilimleri': {
                'Fizik': (0, 7),
                'Kimya': (7, 14),
                'Biyoloji': (14, 20)
            },
            'Sosyal Bilimler': {
                'Tarih': (0, 5),
                'Coğrafya': (5, 10),
                'Felsefe': (10, 15),
                'Din Kültürü ve Ahlak Bilgisi': (15, 20)
            }
        }

        # Türkçe
        dogru = yanlis = bos = 0
        anahtar = cevap_anahtari.get('Türkçe', [])
        ogrenci = ogrenci_cevaplari.get('Türkçe', [])
        for i in range(40):
            c_anahtar = anahtar[i] if i < len(anahtar) else ''
            c_ogrenci = ogrenci[i] if i < len(ogrenci) else ''
            if c_ogrenci == '':
                bos += 1
            elif c_ogrenci == c_anahtar:
                dogru += 1
            else:
                yanlis += 1
        net = dogru - (yanlis / 4)
        sonuc['Türkçe'] = {'dogru': dogru, 'yanlis': yanlis, 'bos': bos, 'net': round(net, 2), 'toplam': 40}

        # Matematik
        dogru = yanlis = bos = 0
        anahtar = cevap_anahtari.get('Matematik', []) or cevap_anahtari.get('Temel Matematik', [])
        ogrenci = ogrenci_cevaplari.get('Matematik', []) or ogrenci_cevaplari.get('Temel Matematik', [])
        for i in range(40):
            c_anahtar = anahtar[i] if i < len(anahtar) else ''
            c_ogrenci = ogrenci[i] if i < len(ogrenci) else ''
            if c_ogrenci == '':
                bos += 1
            elif c_ogrenci == c_anahtar:
                dogru += 1
            else:
                yanlis += 1
        net = dogru - (yanlis / 4)
        sonuc['Matematik'] = {'dogru': dogru, 'yanlis': yanlis, 'bos': bos, 'net': round(net, 2), 'toplam': 40}

        # Fen Bilimleri alt dersler
        fen_anahtar = cevap_anahtari.get('Fen Bilimleri', [])
        fen_ogrenci = ogrenci_cevaplari.get('Fen Bilimleri', [])
        fen_sonuc = {}
        for alt_ders, (start, end) in tyt_dersler['Fen Bilimleri'].items():
            dogru = yanlis = bos = 0
            for i in range(start, end):
                c_anahtar = fen_anahtar[i] if i < len(fen_anahtar) else ''
                c_ogrenci = fen_ogrenci[i] if i < len(fen_ogrenci) else ''
                if c_ogrenci == '':
                    bos += 1
                elif c_ogrenci == c_anahtar:
                    dogru += 1
                else:
                    yanlis += 1
            net = dogru - (yanlis / 4)
            toplam = end - start
            fen_sonuc[alt_ders] = {'dogru': dogru, 'yanlis': yanlis, 'bos': bos, 'net': round(net, 2), 'toplam': toplam}
        # Fen Bilimleri toplam
        toplam_dogru = sum(fen_sonuc[d]['dogru'] for d in fen_sonuc)
        toplam_yanlis = sum(fen_sonuc[d]['yanlis'] for d in fen_sonuc)
        toplam_bos = sum(fen_sonuc[d]['bos'] for d in fen_sonuc)
        toplam_net = sum(fen_sonuc[d]['net'] for d in fen_sonuc)
        sonuc.update(fen_sonuc)
        sonuc['Fen Bilimleri'] = {
            'dogru': toplam_dogru, 'yanlis': toplam_yanlis, 'bos': toplam_bos,
            'net': round(toplam_net, 2), 'toplam': 20
        }

        # Sosyal Bilimler alt dersler
        sosyal_anahtar = cevap_anahtari.get('Sosyal Bilimler', [])
        sosyal_ogrenci = ogrenci_cevaplari.get('Sosyal Bilimler', [])
        sosyal_sonuc = {}
        for alt_ders, (start, end) in tyt_dersler['Sosyal Bilimler'].items():
            dogru = yanlis = bos = 0
            for i in range(start, end):
                c_anahtar = sosyal_anahtar[i] if i < len(sosyal_anahtar) else ''
                c_ogrenci = sosyal_ogrenci[i] if i < len(sosyal_ogrenci) else ''
                if c_ogrenci == '':
                    bos += 1
                elif c_ogrenci == c_anahtar:
                    dogru += 1
                else:
                    yanlis += 1
            net = dogru - (yanlis / 4)
            toplam = end - start
            sosyal_sonuc[alt_ders] = {'dogru': dogru, 'yanlis': yanlis, 'bos': bos, 'net': round(net, 2), 'toplam': toplam}
        # Sosyal Bilimler toplam
        toplam_dogru = sum(sosyal_sonuc[d]['dogru'] for d in sosyal_sonuc)
        toplam_yanlis = sum(sosyal_sonuc[d]['yanlis'] for d in sosyal_sonuc)
        toplam_bos = sum(sosyal_sonuc[d]['bos'] for d in sosyal_sonuc)
        toplam_net = sum(sosyal_sonuc[d]['net'] for d in sosyal_sonuc)
        sonuc.update(sosyal_sonuc)
        sonuc['Sosyal Bilimler'] = {
            'dogru': toplam_dogru, 'yanlis': toplam_yanlis, 'bos': toplam_bos,
            'net': round(toplam_net, 2), 'toplam': 20
        }

    elif tur == 'AYT':
        # Soru dağılımı
        ayt_dersler = {
            'Türk Dili ve Edebiyatı – Sosyal Bilimler 1': {
                'Türk Dili ve Edebiyatı': (0, 24),
                'Tarih-1': (24, 34),
                'Coğrafya-1': (34, 40)
            },
            'Sosyal Bilimler 2': {
                'Tarih-2': (0, 11),
                'Coğrafya-2': (11, 22),
                'Felsefe Grubu': (22, 34),
                'Din Kültürü ve Ahlak Bilgisi': (34, 40)
            },
            'Matematik': (0, 40),
            'Fen Bilimleri': {
                'Fizik': (0, 14),
                'Kimya': (14, 27),
                'Biyoloji': (27, 40)
            }
        }

        # 1. Türk Dili ve Edebiyatı – Sosyal Bilimler 1
        edeb_sos1_anahtar = cevap_anahtari.get('Türk Dili ve Edebiyatı – Sosyal Bilimler 1', [])
        edeb_sos1_ogrenci = ogrenci_cevaplari.get('Türk Dili ve Edebiyatı – Sosyal Bilimler 1', [])
        edeb_sos1_sonuc = {}
        for alt_ders, (start, end) in ayt_dersler['Türk Dili ve Edebiyatı – Sosyal Bilimler 1'].items():
            dogru = yanlis = bos = 0
            for i in range(start, end):
                c_anahtar = edeb_sos1_anahtar[i] if i < len(edeb_sos1_anahtar) else ''
                c_ogrenci = edeb_sos1_ogrenci[i] if i < len(edeb_sos1_ogrenci) else ''
                if c_ogrenci == '':
                    bos += 1
                elif c_ogrenci == c_anahtar:
                    dogru += 1
                else:
                    yanlis += 1
            net = dogru - (yanlis / 4)
            toplam = end - start
            edeb_sos1_sonuc[alt_ders] = {'dogru': dogru, 'yanlis': yanlis, 'bos': bos, 'net': round(net, 2), 'toplam': toplam}
        sonuc.update(edeb_sos1_sonuc)
        sonuc['Türk Dili ve Edebiyatı – Sosyal Bilimler 1'] = {
            'dogru': sum(edeb_sos1_sonuc[d]['dogru'] for d in edeb_sos1_sonuc),
            'yanlis': sum(edeb_sos1_sonuc[d]['yanlis'] for d in edeb_sos1_sonuc),
            'bos': sum(edeb_sos1_sonuc[d]['bos'] for d in edeb_sos1_sonuc),
            'net': round(sum(edeb_sos1_sonuc[d]['net'] for d in edeb_sos1_sonuc), 2),
            'toplam': 40
        }

        # 2. Sosyal Bilimler 2
        sos2_anahtar = cevap_anahtari.get('Sosyal Bilimler 2', [])
        sos2_ogrenci = ogrenci_cevaplari.get('Sosyal Bilimler 2', [])
        sos2_sonuc = {}
        for alt_ders, (start, end) in ayt_dersler['Sosyal Bilimler 2'].items():
            dogru = yanlis = bos = 0
            for i in range(start, end):
                c_anahtar = sos2_anahtar[i] if i < len(sos2_anahtar) else ''
                c_ogrenci = sos2_ogrenci[i] if i < len(sos2_ogrenci) else ''
                if c_ogrenci == '':
                    bos += 1
                elif c_ogrenci == c_anahtar:
                    dogru += 1
                else:
                    yanlis += 1
            net = dogru - (yanlis / 4)
            toplam = end - start
            sos2_sonuc[alt_ders] = {'dogru': dogru, 'yanlis': yanlis, 'bos': bos, 'net': round(net, 2), 'toplam': toplam}
        sonuc.update(sos2_sonuc)
        sonuc['Sosyal Bilimler 2'] = {
            'dogru': sum(sos2_sonuc[d]['dogru'] for d in sos2_sonuc),
            'yanlis': sum(sos2_sonuc[d]['yanlis'] for d in sos2_sonuc),
            'bos': sum(sos2_sonuc[d]['bos'] for d in sos2_sonuc),
            'net': round(sum(sos2_sonuc[d]['net'] for d in sos2_sonuc), 2),
            'toplam': 40
        }

        # 3. Matematik
        mat_anahtar = cevap_anahtari.get('Matematik', [])
        mat_ogrenci = ogrenci_cevaplari.get('Matematik', [])
        dogru = yanlis = bos = 0
        for i in range(40):
            c_anahtar = mat_anahtar[i] if i < len(mat_anahtar) else ''
            c_ogrenci = mat_ogrenci[i] if i < len(mat_ogrenci) else ''
            if c_ogrenci == '':
                bos += 1
            elif c_ogrenci == c_anahtar:
                dogru += 1
            else:
                yanlis += 1
        net = dogru - (yanlis / 4)
        sonuc['Matematik'] = {'dogru': dogru, 'yanlis': yanlis, 'bos': bos, 'net': round(net, 2), 'toplam': 40}

        # 4. Fen Bilimleri alt dersler
        fen_anahtar = cevap_anahtari.get('Fen Bilimleri', [])
        fen_ogrenci = ogrenci_cevaplari.get('Fen Bilimleri', [])
        fen_sonuc = {}
        for alt_ders, (start, end) in ayt_dersler['Fen Bilimleri'].items():
            dogru = yanlis = bos = 0
            for i in range(start, end):
                c_anahtar = fen_anahtar[i] if i < len(fen_anahtar) else ''
                c_ogrenci = fen_ogrenci[i] if i < len(fen_ogrenci) else ''
                if c_ogrenci == '':
                    bos += 1
                elif c_ogrenci == c_anahtar:
                    dogru += 1
                else:
                    yanlis += 1
            net = dogru - (yanlis / 4)
            toplam = end - start
            fen_sonuc[alt_ders] = {'dogru': dogru, 'yanlis': yanlis, 'bos': bos, 'net': round(net, 2), 'toplam': toplam}
        sonuc.update(fen_sonuc)
        sonuc['Fen Bilimleri'] = {
            'dogru': sum(fen_sonuc[d]['dogru'] for d in fen_sonuc),
            'yanlis': sum(fen_sonuc[d]['yanlis'] for d in fen_sonuc),
            'bos': sum(fen_sonuc[d]['bos'] for d in fen_sonuc),
            'net': round(sum(fen_sonuc[d]['net'] for d in fen_sonuc), 2),
            'toplam': 40
        }

    # Toplam net
    toplam_net = sum(v['net'] for v in sonuc.values() if v.get('net') is not None)
    sonuc['Toplam'] = {
        'dogru': None,
        'yanlis': None,
        'bos': None,
        'net': round(toplam_net, 2),
        'toplam': None
    }

    return sonuc
