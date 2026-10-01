"""
Faza 3 — analiza skanu planszy (human-in-the-loop).

Wykrywa linie (Hough) i proponuje rolę: cut vs fold.
To są SUGESTIE do weryfikacji — nie gotowy model.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


def analyze_scan(
    image_path: Path,
    output_dir: Path,
    max_lines: int = 80,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = Path(image_path)

    if not image_path.exists():
        return {"ok": False, "error": f"File not found: {image_path}"}

    # PDF nie obsługujemy w MVP — tylko raster
    suffix = image_path.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}:
        return {
            "ok": False,
            "error": f"Unsupported image type: {suffix}. Use JPG/PNG/WEBP.",
        }

    bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if bgr is None:
        return {"ok": False, "error": "Cannot decode image"}

    h, w = bgr.shape[:2]
    # Downscale dużych skanów dla stabilności
    scale = 1.0
    max_side = 1800
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        h, w = bgr.shape[:2]

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 60, 160, apertureSize=3)

    lines_p = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=60,
        minLineLength=max(30, int(min(w, h) * 0.04)),
        maxLineGap=8,
    )

    overlay = bgr.copy()
    suggestions: list[dict] = []

    if lines_p is not None:
        # Sortuj po długości, weź top N
        scored: list[tuple[float, tuple[int, int, int, int], str]] = []
        for x1, y1, x2, y2 in lines_p.reshape(-1, 4):
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            length = float(np.hypot(x2 - x1, y2 - y1))
            role = _classify_line(gray, x1, y1, x2, y2)
            scored.append((length, (x1, y1, x2, y2), role))
        scored.sort(key=lambda t: t[0], reverse=True)

        for length, (x1, y1, x2, y2), role in scored[:max_lines]:
            color = (0, 0, 220) if role == "cut_line" else (0, 180, 255)  # BGR
            thickness = 2 if role == "cut_line" else 1
            if role == "fold_line":
                _draw_dashed(overlay, (x1, y1), (x2, y2), color, thickness)
            else:
                cv2.line(overlay, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)

            # współrzędne w oryginalnej skali obrazu wejściowego (po resize = bieżące)
            suggestions.append(
                {
                    "role": role,
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "length_px": round(length, 1),
                    "confidence": round(_confidence(length, min(w, h)), 2),
                }
            )

    # Legenda
    cv2.rectangle(overlay, (8, 8), (280, 70), (255, 255, 255), -1)
    cv2.putText(overlay, "SUGESTIE (weryfikuj recznie)", (14, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 1)
    cv2.line(overlay, (14, 42), (40, 42), (0, 0, 220), 2)
    cv2.putText(overlay, "cut (ciecie)", (46, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1)
    cv2.line(overlay, (150, 42), (176, 42), (0, 180, 255), 1)
    cv2.putText(overlay, "fold (giecie)", (182, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1)

    overlay_path = output_dir / "scan_overlay.png"
    json_path = output_dir / "scan_suggestions.json"
    cv2.imwrite(str(overlay_path), overlay)

    payload = {
        "ok": True,
        "image_size": {"width": w, "height": h, "scale_from_original": scale},
        "line_count": len(suggestions),
        "cut_count": sum(1 for s in suggestions if s["role"] == "cut_line"),
        "fold_count": sum(1 for s in suggestions if s["role"] == "fold_line"),
        "suggestions": suggestions,
        "note": "Sugestie CV — wymagają weryfikacji człowieka. Nie generują gotowego modelu.",
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "overlay_path": str(overlay_path.resolve()),
        "suggestions_path": str(json_path.resolve()),
        "line_count": payload["line_count"],
        "cut_count": payload["cut_count"],
        "fold_count": payload["fold_count"],
        "image_size": payload["image_size"],
        "note": payload["note"],
    }


def _classify_line(gray: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> str:
    """
    Heurystyka:
    - ciemniejszy, ciągły kontur → cut
    - jaśniejszy / przerywany profil → fold
    """
    samples = _sample_along(gray, x1, y1, x2, y2, n=24)
    if not samples:
        return "cut_line"
    mean = float(np.mean(samples))
    std = float(np.std(samples))
    # przerywane linie mają większą wariancję jasności wzdłuż odcinka
    if std > 28 and mean > 90:
        return "fold_line"
    if mean > 140:
        return "fold_line"
    return "cut_line"


def _sample_along(gray: np.ndarray, x1: int, y1: int, x2: int, y2: int, n: int = 20) -> list[float]:
    h, w = gray.shape[:2]
    vals: list[float] = []
    for i in range(n):
        t = i / max(n - 1, 1)
        x = int(round(x1 + (x2 - x1) * t))
        y = int(round(y1 + (y2 - y1) * t))
        if 0 <= x < w and 0 <= y < h:
            vals.append(float(gray[y, x]))
    return vals


def _confidence(length: float, min_side: float) -> float:
    return min(0.95, 0.35 + length / max(min_side, 1) * 0.8)


def _draw_dashed(img: np.ndarray, p1: tuple[int, int], p2: tuple[int, int], color, thickness: int) -> None:
    x1, y1 = p1
    x2, y2 = p2
    dist = float(np.hypot(x2 - x1, y2 - y1))
    if dist < 1:
        return
    dash, gap = 8, 6
    n = int(dist // (dash + gap)) + 1
    for i in range(n):
        a = (i * (dash + gap)) / dist
        b = min(1.0, (i * (dash + gap) + dash) / dist)
        if a >= 1:
            break
        xa, ya = int(x1 + (x2 - x1) * a), int(y1 + (y2 - y1) * a)
        xb, yb = int(x1 + (x2 - x1) * b), int(y1 + (y2 - y1) * b)
        cv2.line(img, (xa, ya), (xb, yb), color, thickness, cv2.LINE_AA)
