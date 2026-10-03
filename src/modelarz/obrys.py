"""Obrys bryły z rysunku-planu: na arkuszu z kilkoma rzutami znajduje rzut boczny (po proporcjach
długość : wysokość znanych z danych technicznych), wycina linie wymiarowe i opisy, a z tego,
co zostaje, bierze zewnętrzny kontur w metrach oryginału."""
from __future__ import annotations

import cv2
import numpy as np
from shapely.geometry import LineString


def _ink(gray: np.ndarray) -> np.ndarray:
    if gray.mean() < 110:          # rysunek jasny na ciemnym tle (np. „blueprint”)
        gray = 255 - gray
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return ink


def side_profile(data: bytes, length: float, height: float, tol: float = 0.14):
    v = views(data, length, height)
    return (v["side"], v["preview"]) if v else (None, None)


def views(data: bytes, length: float, height: float, width: float | None = None):
    """Rzuty rozpoznane na planie: {"side": [[x, z]], "top": [[x, połowa szerokości]] | None,
    "front": [[z, połowa szerokości]] | None, "preview": PNG} albo None."""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:            # np. GIF — bierzemy pierwszą klatkę
        import os
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as fh:
            fh.write(data)
        cap = cv2.VideoCapture(fh.name)
        ok, img = cap.read()
        cap.release()
        os.unlink(fh.name)
        if not ok:
            return None
    h0, w0 = img.shape[:2]
    k = 1000.0 / max(h0, w0)
    if k < 1 or k > 1.6:           # wspólna rozdzielczość robocza
        img = cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_CUBIC)
    ink = _ink(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    # 1. rysunki odręczne i skany: usuwamy linie wymiarowe śmielej i wypełniamy zamknięty kontur;
    # 2. bryły o długich prostych krawędziach (ich własne linie wyglądają jak wymiarowe): łagodniej, „kurtyną”.
    for div, curtain in ((6, False), (3, True)):
        out = _extract(img, ink, length, height, div, curtain)
        if out[0]:
            pts, prev, s, box, solids = out
            res = {"side": pts, "top": None, "front": None}
            if width:
                for (x, y, m) in solids:
                    if abs(x - box[0]) < 3 and abs(y - box[1]) < box[3]:
                        continue                               # to sam rzut boczny
                    hpx, wpx = m.shape
                    lr = (m & m[:, ::-1]).sum() / max(1, (m | m[:, ::-1]).sum())
                    ud = (m & m[::-1]).sum() / max(1, (m | m[::-1]).sum())
                    if res["top"] is None and abs(wpx * s - length) / length < 0.08 \
                            and abs(hpx * s - width) / width < 0.18 and ud > 0.8:
                        half = m.sum(axis=0) * s / 2
                        ln = LineString([(cx * s, float(half[cx])) for cx in range(wpx)]).simplify(0.004 * length)
                        res["top"] = [[round(a, 4), round(b, 4)] for a, b in ln.coords]
                        cv2.rectangle(prev, (int(x), int(y)), (int(x + wpx), int(y + hpx)), (200, 120, 30), 2)
                    elif res["front"] is None and abs(wpx * s - width) / width < 0.18 \
                            and 0.7 * height < hpx * s < 1.2 * height and lr > 0.75:
                        half = m.sum(axis=1) * s / 2
                        ln = LineString([(height - r * s, float(half[r])) for r in range(hpx)]).simplify(0.004 * length)
                        res["front"] = sorted([round(a, 4), round(b, 4)] for a, b in ln.coords)
                        cv2.rectangle(prev, (int(x), int(y)), (int(x + wpx), int(y + hpx)), (30, 160, 60), 2)
            ok, png = cv2.imencode(".png", prev)
            res["preview"] = png.tobytes() if ok else None
            return res
    return None


def _extract(img, ink, length, height, div, curtain):
    H, W = ink.shape
    lines = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (W // div, 1))) \
        | cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, H // div)))
    body = cv2.subtract(ink, cv2.dilate(lines, np.ones((3, 3), np.uint8)))
    # cyfry wymiarów i groty strzałek: drobne, osobne składowe
    n, lab, stats, _ = cv2.connectedComponentsWithStats(body, 8)
    small = [i for i in range(1, n) if max(stats[i][2], stats[i][3]) < 0.035 * W]
    body[np.isin(lab, small)] = 0
    blob = cv2.morphologyEx(body, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(blob, 8)
    best = None
    solids = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if w < 0.25 * W or h < 20:
            continue
        mask = lab[y:y + h, x:x + w] == i
        s = length / w
        band = int(round(height / s))                 # wysokość pojazdu w pikselach przy tej skali
        # „kurtyna”: wszystko pod najwyższym punktem bryły w każdej kolumnie; dół sylwetki nas nie obchodzi
        kk = max(5, int(0.035 * w)) | 1               # ścinamy cienkie wypustki: resztki wymiarów, anteny, lusterka
        ell = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kk, kk))
        if not curtain:    # zamknięty kontur wypełniony w środku; cienkie linie odpadają przy otwarciu
            m8 = cv2.morphologyEx(mask.astype(np.uint8) * 255, cv2.MORPH_CLOSE,
                                  cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)))
            cnts, _ = cv2.findContours(m8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            solid = np.zeros_like(m8)
            cv2.drawContours(solid, [max(cnts, key=cv2.contourArea)], -1, 255, -1)
            mask = cv2.morphologyEx(solid, cv2.MORPH_OPEN, ell) > 0
            if not mask.any():
                continue
            cols = np.nonzero(mask.any(axis=0))[0]
            x, w, mask = x + cols.min(), cols.max() - cols.min() + 1, mask[:, cols.min():cols.max() + 1]
            rows = np.nonzero(mask.any(axis=1))[0]
            solids.append((x, y + rows.min(), mask[rows.min():rows.max() + 1]))
            if w < 0.25 * W:
                continue
            s = length / w
            band = int(round(height / s))
        first = np.where(mask.any(axis=0), mask.argmax(axis=0), h)
        fill = (np.arange(max(h, band))[:, None] >= first[None, :]).astype(np.uint8) * 255
        fill = cv2.morphologyEx(fill, cv2.MORPH_OPEN, ell)
        if not fill.any():
            continue
        y_top = int(np.argmax(fill.any(axis=1)))
        fill = fill[y_top:y_top + band]
        if fill.shape[0] < band * 0.9:
            continue
        flipped = fill[::-1]
        sym = (fill & flipped).sum() / max(1, (fill | flipped).sum())   # rzut z góry daje pełny prostokąt
        if sym > 0.86 or fill.mean() / 255 < 0.45:
            continue
        if best is None or w > best[4]:
            best = (sym, fill, x, y + y_top, w, band)
    if best is None:
        return None, None, None, None, None
    _, fill, x, y, w, h = best
    # górna obwiednia: dla każdej kolumny najwyższy punkt bryły, w metrach od ziemi
    top = np.array([np.argmax(fill[:, cx] > 0) if fill[:, cx].any() else h for cx in range(w)], float)
    s = length / w
    line = LineString([(cx * s, height - top[cx] * s) for cx in range(w)]).simplify(0.004 * length)
    pts = [[round(px, 4), round(max(pz, 0.0), 4)] for px, pz in line.coords]
    if len(pts) < 6:
        return None, None, None, None, None
    # Wyrwa w obwiedni (np. niewidoczna na skanie linia maski) znaczy, że rysunek się nie nadaje.
    zs = height - top * s
    span = max(1, int(0.07 * w))
    for cx in range(span, w - span, max(1, w // 60)):
        if zs[cx] < min(zs[cx - span:cx].max(), zs[cx + 1:cx + span].max()) - 0.15 * height:
            return None, None, None, None, None
    prev = img.copy()
    c = np.array([[cx, top[cx]] for cx in range(0, w, 2)])
    cv2.polylines(prev, [(c + [x, y]).astype(np.int32)], False, (40, 40, 220), 3)
    return pts, prev, s, (x, y, w, h), solids
