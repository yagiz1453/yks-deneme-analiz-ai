# yks-deneme-analiz-ai
# 🚀 YKS Deneme Analiz & AI Koçluk Sistemi

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Framework-Flask-green)
![OpenCV](https://img.shields.io/badge/Library-OpenCV-red)
![License](https://img.shields.io/badge/License-GPLv3-orange)

**yks-deneme-analiz-ai**; lise öğrencileri için geliştirilmiş, deneme sınavlarını optik form üzerinden otomatik okuyan, detaylı istatistiksel analizler sunan ve yapay zeka destekli kişisel koçluk yapan kapsamlı bir web uygulamasıdır.

Bu proje, görüntü işleme algoritmaları ve modern web teknolojilerini birleştirerek eğitim süreçlerindeki veri takibini dijitalleştirmeyi hedefler.

## 🌟 Özellikler

* **📸 Optik Okuma (OCR):** OpenCV ve Tesseract altyapısı ile yüklenen optik formların görüntü işleme teknikleriyle otomatik okunması, şıkların algılanması ve puanlanması.
* **🤖 Akıllı Koçluk Sistemi:** Öğrencinin deneme sonuçlarını analiz edip, LLM (Groq API) entegrasyonu üzerinden kişiselleştirilmiş çalışma tavsiyeleri veren canlı sohbet asistanı.
* **📊 Detaylı Analiz:** TYT ve AYT bazlı net hesaplama, ders bazlı başarı grafikleri ve zaman serisi (gelişim) analizleri.
* **🔒 Güvenli Altyapı:** Rol tabanlı yetkilendirme (Admin/User), CSRF koruması, güvenli oturum yönetimi ve hashlenmiş veri güvenliği.
* **⚡ Modern Mimari:** Flask Blueprints ile modüler yapı, asenkron dosya temizleme işlemleri (Threading) ve Server-Sent Events (SSE) ile kesintisiz veri akışı.

## 🛠️ Teknolojiler

* **Backend:** Python, Flask
* **Veritabanı:** SQLite
* **Görüntü İşleme:** OpenCV, Pytesseract, PDF2Image
* **Veri Analizi:** Pandas, NumPy
* **Yapay Zeka Entegrasyonu:** Groq API
* **Frontend:** HTML5, CSS3, JavaScript (Jinja2 Templates)

## ⚠️ Sistem Gereksinimleri

Bu proje OCR işlemleri için **Tesseract** ve PDF işlemleri için **Poppler** araçlarına ihtiyaç duyar. Python kütüphanelerini yüklemeden önce bunları işletim sisteminize kurmalısınız.

### 🪟 Windows İçin
1.  **Tesseract OCR:** İndirin ve kurun. Kurulum yolunu (örn: `C:\Program Files\Tesseract-OCR`) kopyalayıp `.env` dosyasına eklemeyi unutmayın.
2.  **Poppler:** `pdf2image` için gereklidir. İndirin, zipten çıkarın ve `bin` klasörünü bilgisayarınızın "Path" değişkenlerine ekleyin.

### 🐧 Linux (Ubuntu/Debian) İçin
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr poppler-utils libgl1
    ```

## ⚙️ Kurulum

Projeyi yerel makinenizde çalıştırmak için aşağıdaki adımları izleyin:

1.  **Repoyu klonlayın:**
    ```bash
    git clone https://github.com/yagiz1453/yks-deneme-analiz-ai.git
    cd yks-deneme-analiz-ai
    ```

2.  **Sanal ortam oluşturun ve aktif edin:**
    ```bash
    # Windows için
    python -m venv venv
    venv\Scripts\activate

    # Linux/Mac için
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Gereksinimleri yükleyin:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Ortam değişkenlerini (.env) ayarlayın:**
    Ana dizinde `.env` dosyası oluşturun ve aşağıdaki değerleri girin:
    ```env
    SECRET_KEY=gizli_anahtariniz_buraya
    GROQ_API_KEY=yapay_zeka_api_key
    
    # E-posta servisi için (Gmail App Password)
    GMAIL_USER=mailiniz@gmail.com
    GMAIL_APP_PASSWORD=uygulama_sifresi
    
    # Admin paneli girişi için
    ADMIN_USERNAME=admin
    ADMIN_PASSWORD=admin_sifresi_hashli
    
    # Windows kullanıyorsanız Tesseract yolu (Linux için boş bırakılabilir)
    TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
    ```

5.  **Uygulamayı başlatın:**
    ```bash
    python app.py
    ```
    Tarayıcınızda `http://localhost:5000` adresine gidin.

## 📄 Lisans

Bu proje **GNU GPLv3** lisansı ile lisanslanmıştır. Açık kaynak kodlu olarak geliştirilebilir ve dağıtılabilir, ancak bu projeyi temel alan çalışmaların da açık kaynak olması gerekmektedir.
