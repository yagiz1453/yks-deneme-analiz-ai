import cv2
import numpy as np

class InteractiveROISelector:
    def __init__(self, image):
        self.image = image
        self.clone = image.copy()
        self.roi = None
        self.drawing = False
        self.start_point = None
        self.end_point = None

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_point = (x, y)
            self.end_point = (x, y)

        elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
            self.end_point = (x, y)

        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            self.end_point = (x, y)

    def run(self, window_name="Bölge Seçimi"):
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)  # Boyutlandırılabilir pencere
        cv2.setMouseCallback(window_name, self.mouse_callback)

        print("\n[SEÇİM EKRANI]")
        print("- Sol tık + sürükle: seçim yap")
        print("- ENTER: onayla, ESC: iptal")

        while True:
            display_img = self.clone.copy()
            if self.start_point and self.end_point:
                cv2.rectangle(display_img, self.start_point, self.end_point, (0, 255, 0), 2)
            cv2.imshow(window_name, display_img)

            key = cv2.waitKey(1) & 0xFF
            if key == 13 or key == 10:  # Enter
                if self.start_point and self.end_point:
                    x1, y1 = self.start_point
                    x2, y2 = self.end_point
                    x_min, x_max = sorted([x1, x2])
                    y_min, y_max = sorted([y1, y2])
                    self.roi = (x_min, y_min, x_max - x_min, y_max - y_min)
                break
            elif key == 27:  # ESC
                self.roi = None
                break

        cv2.destroyWindow(window_name)
        return self.roi

def read_answers_and_stats(img, x, y, w, h, rows=40, cols=5, threshold=50):
    crop = img[y:y+h, x:x+w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    cell_w = w / cols
    cell_h = h / rows

    answers = {}
    koyuluk_degerleri = []

    for row in range(rows):
        y1 = int(row * cell_h)
        y2 = int((row + 1) * cell_h)
        max_darkness = 0
        selected_col = None

        for col in range(cols):
            x1 = int(col * cell_w)
            x2 = int((col + 1) * cell_w)
            cell = gray[y1:y2, x1:x2]
            mean_val = np.mean(cell)
            darkness = 255 - mean_val

            if darkness > max_darkness and darkness > threshold:
                max_darkness = darkness
                selected_col = col

        if selected_col is not None:
            answers[row + 1] = chr(ord('A') + selected_col)
            koyuluk_degerleri.append(max_darkness)
        else:
            answers[row + 1] = '-'

    if koyuluk_degerleri:
        max_koyuluk = max(koyuluk_degerleri)
        min_koyuluk = min(koyuluk_degerleri)
        ort_koyuluk = sum(koyuluk_degerleri) / len(koyuluk_degerleri)
    else:
        max_koyuluk = min_koyuluk = ort_koyuluk = 0

    roi_coords = (x, y, w, h)

    return answers, {
        "max_koyuluk": max_koyuluk,
        "min_koyuluk": min_koyuluk,
        "ort_koyuluk": ort_koyuluk,
        "roi_coords": roi_coords,
        "isaretlenen_adet": len(koyuluk_degerleri)
    }


def process_all_dersler(img):
    DERSLER = [
        ("Türkçe", 40),
        ("Sosyal Bilimler", 40),
        ("Temel Matematik", 40),
        ("Fen Bilimleri", 40),
    ]

    results = {}
    for ders_adi, soru_sayisi in DERSLER:
        print(f"\n{ders_adi} alanını seçin:")
        selector = InteractiveROISelector(img)
        roi = selector.run(f"{ders_adi} alanını seçin ve ENTER'a basın")
        if roi is None:
            print(f"{ders_adi} için seçim yapılmadı, atlanıyor.")
            continue
        x, y, w, h = roi
        answers, stats = read_answers_and_stats(img, x, y, w, h, rows=soru_sayisi)
        results[ders_adi] = {
            "answers": answers,
            "stats": stats,
        }
    return results
