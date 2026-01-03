import cv2
import pytesseract
from PIL import Image
import numpy as np
from pdf2image import convert_from_path
import os
from dotenv import load_dotenv

load_dotenv()

# Eğer .env dosyasında TESSERACT_CMD varsa onu kullan, yoksa varsayılanı (Linux yolunu) al
tesseract_path = os.environ.get("TESSERACT_CMD", "/usr/bin/tesseract")
pytesseract.pytesseract.tesseract_cmd = tesseract_path

def extract_text_from_region(file_path, x, y, w, h):
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.pdf':
        images = convert_from_path(file_path)
        if not images:
            raise ValueError("PDF sayfası okunamadı.")
        pil_image = images[0]
    else:
        pil_image = Image.open(file_path)

    image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    roi = image[y:y+h, x:x+w]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inverted = cv2.bitwise_not(thresh)

    config = r'--psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    text = pytesseract.image_to_string(inverted, config=config)

    return text
