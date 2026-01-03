import cv2
import numpy as np

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
