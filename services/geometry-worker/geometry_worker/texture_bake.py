"""Generacja bitmap schematów malowania — wygląd jak na planszy wycinanki, nie „szara siatka”."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


def _rgba(color, default_a: int = 255) -> tuple[int, int, int, int]:
    """Normalizuj kolor z AI (listy, float 0–1 alpha) do int RGBA."""
    if color is None:
        return (128, 128, 128, default_a)
    vals = list(color)
    while len(vals) < 3:
        vals.append(0)
    r = int(round(float(vals[0])))
    g = int(round(float(vals[1])))
    b = int(round(float(vals[2])))
    if len(vals) >= 4:
        a = float(vals[3])
        a = int(round(a * 255)) if 0 <= a <= 1 else int(round(a))
    else:
        a = default_a
    return (
        max(0, min(255, r)),
        max(0, min(255, g)),
        max(0, min(255, b)),
        max(0, min(255, a)),
    )


def _rgb(color) -> tuple[int, int, int]:
    r, g, b, _ = _rgba(color)
    return r, g, b


# Domyślne receptury (AI może nadpisać przez paint_recipe w params)
DEFAULT_PAINT: dict = {
    "base_finish": "aluminum_matte",
    "panel_modulation": True,
    "anti_glare_nose": True,
    "exhaust_stains": True,
    "wing_walkways": True,
    "us_insignia": {"wing_upper": True, "fuse_rear": True},
    "polka_tips": False,
    "canopy": "framed_glass",
    "serial_style": "buzz_number",
    "buzz_number": "FT-274",
    "colors": {
        "aluminum": (208, 211, 216),
        "aluminum_shade": (148, 152, 160),
        "aluminum_hi": (236, 238, 242),
        "anti_glare": (42, 48, 36),
        "exhaust": (72, 62, 52),
        "walkway": (55, 55, 58),
        "glass": (120, 165, 195, 110),
        "frame": (35, 38, 42),
        "accent_blue": (28, 62, 145),
        "od": (72, 82, 52),
        "neutral_gray": (118, 122, 126),
    },
}

SCHEMES: dict[str, dict] = {
    "korea_aluminum": {
        "label": "F-51D Korea — aluminium lacquer (matowy srebrny)",
        "era": "Korea 1950–53",
        "notes": "Matowe aluminium po remoncie, czarny anti-glare, exhaust stains.",
        "paint": {
            **DEFAULT_PAINT,
            "polka_tips": False,
        },
        "refs": [
            "https://thescalemodelhangar.com/2021/06/29/the-f-51d-mustang-in-korea/",
        ],
    },
    "korea_45ths_polka": {
        "label": "RF/F-51D 45th TRS „Polka Dot” (Korea)",
        "era": "Korea ~1952",
        "notes": "Matowe aluminium + niebieskie tipy/spinner w białe kropki (45th TRS).",
        "paint": {
            **DEFAULT_PAINT,
            "polka_tips": True,
            "buzz_number": "FT-190",
        },
        "refs": [
            "https://www.koreanwar.org/html/units/usaf/45trs.htm",
            "https://modelingmadness.com/review/korean/cleaverrf51.htm",
        ],
    },
    "korea_od_gray": {
        "label": "F-51 wczesny — OD / Neutral Gray",
        "era": "przejściowy",
        "notes": "Olive drab góra, neutral gray spód.",
        "paint": {
            **DEFAULT_PAINT,
            "base_finish": "od_gray",
            "polka_tips": False,
            "anti_glare_nose": False,
        },
        "refs": [],
    },
}


def list_schemes() -> list[dict]:
    return [
        {
            "key": k,
            "label": v["label"],
            "era": v["era"],
            "notes": v["notes"],
            "refs": v.get("refs", []),
        }
        for k, v in SCHEMES.items()
    ]


def _merge_paint(scheme: dict, override: dict | None) -> dict:
    paint = {**DEFAULT_PAINT, **(scheme.get("paint") or {})}
    if not override:
        return paint
    out = {**paint, **{k: v for k, v in override.items() if k != "colors"}}
    if "colors" in override and isinstance(override["colors"], dict):
        base_c = dict(paint.get("colors") or {})
        for k, v in override["colors"].items():
            if isinstance(v, (list, tuple)):
                # zachowaj alpha jeśli 4 kanały
                if len(v) >= 4:
                    base_c[k] = _rgba(v)
                else:
                    base_c[k] = _rgb(v)
            else:
                base_c[k] = v
        out["colors"] = base_c
    # deep-ish us_insignia
    if "us_insignia" in override and isinstance(override["us_insignia"], dict):
        out["us_insignia"] = {**(paint.get("us_insignia") or {}), **override["us_insignia"]}
    return out


def bake_scheme_textures(
    output_dir: Path,
    scheme_key: str,
    panels: list,
    px_per_mm: float = 12.0,
    paint_recipe: dict | None = None,
) -> dict[str, Path]:
    scheme = SCHEMES.get(scheme_key, SCHEMES["korea_aluminum"])
    paint = _merge_paint(scheme, paint_recipe)
    colors = paint["colors"]
    output_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    rng = random.Random(hash(scheme_key) & 0xFFFF)

    for panel in panels:
        if panel.name.startswith("former_") or panel.name.startswith("rib_") or panel.name.startswith("spar_") or panel.name == "keel":
            continue

        w = max(16, int(panel.w * px_per_mm))
        h = max(16, int(panel.h * px_per_mm))
        is_lower = (
            "lower" in panel.name
            or panel.name.endswith("_le")
            or panel.name in {"radiator_scoop"}
            or panel.name.startswith("flap_")
            or panel.name.startswith("well_")
        )

        # opcjonalnie AI image (A1111) — fallback procedural
        ai_img = None
        try:
            from .ai_image import try_generate_panel_image, panel_paint_prompt

            ai_img = try_generate_panel_image(
                panel_paint_prompt(
                    panel.name,
                    scheme["label"],
                    str(paint.get("base_finish", "aluminum_matte")),
                ),
                w,
                h,
            )
        except Exception:
            ai_img = None

        if panel.name.startswith("canopy_"):
            img = _bake_canopy(w, h, paint)
        elif ai_img is not None:
            img = ai_img
            _apply_panel_details(ImageDraw.Draw(img), img, panel, w, h, paint, rng)
        else:
            img = _bake_metal_panel(w, h, paint, is_lower=is_lower, rng=rng)
            draw = ImageDraw.Draw(img)
            _apply_panel_details(draw, img, panel, w, h, paint, rng)

        mask = _cut_mask(panel, w, h, px_per_mm)
        img.putalpha(mask)

        path = output_dir / f"tex_{panel.name}.png"
        img.save(path, "PNG")
        out[panel.name] = path

    (output_dir / "scheme.json").write_text(
        json.dumps(
            {
                "key": scheme_key,
                "label": scheme["label"],
                "notes": scheme["notes"],
                "refs": scheme.get("refs", []),
                "paint_recipe": _jsonable(paint),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return out


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def _bake_metal_panel(
    w: int, h: int, paint: dict, is_lower: bool, rng: random.Random
) -> Image.Image:
    c = paint["colors"]
    finish = paint.get("base_finish", "aluminum_matte")

    if finish == "od_gray":
        base = _rgb(c["neutral_gray"] if is_lower else c["od"])
        shade = tuple(max(0, x - 25) for x in base)
        hi = tuple(min(255, x + 20) for x in base)
    else:
        alum = _rgb(c["aluminum"])
        base = alum if not is_lower else tuple(max(0, int(x * 0.92)) for x in alum)
        shade = _rgb(c["aluminum_shade"])
        hi = _rgb(c.get("aluminum_hi", (236, 238, 242)))

    img = Image.new("RGBA", (w, h), (*base, 255))
    px = img.load()

    # modulacja paneli + delikatny „metal” gradient
    if paint.get("panel_modulation", True):
        bands = max(3, w // 40)
        for x in range(w):
            band = (x // max(1, w // bands)) % 2
            # pionowy highlight (jak światło na blachę)
            t = x / max(1, w - 1)
            vert = 1.0 + 0.08 * math.sin(t * math.pi)
            for y in range(h):
                n = 1.0 + (rng.random() - 0.5) * 0.04
                if band:
                    n *= 0.94
                n *= vert
                # lekki cień ku krawędziom chord
                edge = 1.0 - 0.12 * abs(y / max(1, h - 1) - 0.5) * 2
                n *= edge
                r, g, b, a = px[x, y]
                if n >= 1:
                    f = min(1.0, n - 1.0) / 0.15 if n > 1 else 0
                    f = min(1.0, (n - 1.0) * 4) if n > 1 else 0
                    r = int(r + (hi[0] - r) * min(1, (n - 1) * 5))
                    g = int(g + (hi[1] - g) * min(1, (n - 1) * 5))
                    b = int(b + (hi[2] - b) * min(1, (n - 1) * 5))
                else:
                    r = int(r + (shade[0] - r) * (1 - n) * 1.2)
                    g = int(g + (shade[1] - g) * (1 - n) * 1.2)
                    b = int(b + (shade[2] - b) * (1 - n) * 1.2)
                px[x, y] = (
                    max(0, min(255, r)),
                    max(0, min(255, g)),
                    max(0, min(255, b)),
                    255,
                )

    draw = ImageDraw.Draw(img)
    # bardzo subtelne linie stacji (nie „kratka UV”)
    shade4 = (*shade, 55)
    step = max(28, w // 5)
    for x in range(step, w, step):
        draw.line([(x, 2), (x, h - 2)], fill=shade4, width=1)
    step_y = max(22, h // 4)
    for y in range(step_y, h, step_y):
        draw.line([(2, y), (w - 2, y)], fill=(*shade, 40), width=1)

    return img


def _bake_canopy(w: int, h: int, paint: dict) -> Image.Image:
    c = paint["colors"]
    glass = _rgba(c["glass"], default_a=120)
    frame = _rgb(c["frame"])
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    inset = max(3, min(w, h) // 12)
    draw.rounded_rectangle(
        [inset, inset, w - inset, h - inset],
        radius=max(2, inset),
        fill=glass,
    )
    draw.rounded_rectangle(
        [1, 1, w - 2, h - 2],
        radius=max(2, inset),
        outline=(*frame, 255),
        width=max(2, inset // 2),
    )
    mid = w // 2
    draw.line([(mid, inset), (mid, h - inset)], fill=(*frame, 255), width=max(2, inset // 2))
    draw.arc(
        [inset + 2, inset + 2, w // 2, h // 2],
        start=200,
        end=320,
        fill=(255, 255, 255, 90),
        width=2,
    )
    return img


def _apply_panel_details(
    draw: ImageDraw.ImageDraw,
    img: Image.Image,
    panel,
    w: int,
    h: int,
    paint: dict,
    rng: random.Random,
) -> None:
    c = paint["colors"]
    name = panel.name
    insignia = paint.get("us_insignia") or {}
    anti = _rgb(c["anti_glare"])
    exhaust = _rgb(c["exhaust"])
    walkway = _rgb(c["walkway"])
    accent = _rgba(c["accent_blue"])
    shade = _rgb(c["aluminum_shade"])

    # anti-glare — nos + przednie sekcje kadłuba
    if paint.get("anti_glare_nose"):
        front = name == "nose_cowling" or (
            name.startswith(("fuse_L", "fuse_R"))
            and any(x in name for x in ("A", "B", "C"))
        )
        if front:
            ag = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ad = ImageDraw.Draw(ag)
            ad.rectangle([0, 0, w, int(h * 0.30)], fill=(*anti, 210))
            img.alpha_composite(ag)
            draw = ImageDraw.Draw(img)

    # exhaust
    if paint.get("exhaust_stains") and (
        name.startswith("fuse_L") or name.startswith("fuse_R") or name == "nose_cowling"
    ):
        # tylko przednie sekcje (A–D)
        if any(s in name for s in ("A", "B", "C", "D", "nose")):
            stain = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            sd = ImageDraw.Draw(stain)
            for i in range(5):
                y0 = int(h * (0.35 + i * 0.08))
                x0 = int(w * 0.05)
                x1 = int(w * (0.55 + i * 0.08))
                alpha = 110 - i * 15
                sd.ellipse(
                    [x0, y0, x1, y0 + max(6, h // 10)],
                    fill=(*exhaust, max(30, alpha)),
                )
            stain = stain.filter(ImageFilter.GaussianBlur(radius=max(1, h // 40)))
            img.alpha_composite(stain)
            draw = ImageDraw.Draw(img)

    # walkway skrzydła (root)
    if paint.get("wing_walkways") and "wing_" in name and "upper" in name:
        ww = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        wd = ImageDraw.Draw(ww)
        band = max(8, h // 7)
        if "left" in name:
            wd.rectangle([0, h - band - 2, int(w * 0.28), h - 2], fill=(*walkway, 210))
        else:
            wd.rectangle(
                [int(w * 0.72), h - band - 2, w, h - 2], fill=(*walkway, 210)
            )
        img.alpha_composite(ww)
        draw = ImageDraw.Draw(img)

    # polka tips 45th TRS
    if paint.get("polka_tips"):
        if "wing_" in name and "upper" in name:
            tip = max(12, w // 5)
            if "left" in name:
                draw.rectangle([w - tip, 0, w, h], fill=accent)
                _polka(draw, w - tip, 0, tip, h)
            else:
                draw.rectangle([0, 0, tip, h], fill=accent)
                _polka(draw, 0, 0, tip, h)
        if name in {"fin", "rudder"} or "tailplane" in name:
            band = max(10, h // 5)
            draw.rectangle([0, 0, w, band], fill=accent)
            _polka(draw, 0, 0, w, band)
        if name.startswith("spinner_"):
            draw.rectangle([0, 0, w, h], fill=accent)
            _polka(draw, 0, 0, w, h)

    # insignia
    if insignia.get("wing_upper") and "wing_" in name and "upper" in name:
        _us_insignia(draw, int(w * 0.45), int(h * 0.48), max(10, min(w, h) // 5))
    if insignia.get("fuse_rear") and name.startswith(("fuse_L", "fuse_R")):
        # tylne sekcje E–J
        if any(s in name for s in ("E", "F", "G", "H", "I", "J")):
            _us_insignia(draw, int(w * 0.55), int(h * 0.5), max(8, min(w, h) // 4))

    # buzz number
    if paint.get("serial_style") == "buzz_number" and name.startswith(("fuse_L", "fuse_R")):
        if any(s in name for s in ("F", "G", "H", "I")):
            _draw_text(
                draw,
                paint.get("buzz_number") or "FT-274",
                int(w * 0.12),
                int(h * 0.55),
                max(10, h // 5),
                fill=(25, 25, 28, 230),
            )

    # gęstsze nity wzdłuż krawędzi (jak na planszach)
    if min(w, h) > 40:
        step = max(6, min(w, h) // 18)
        for x in range(step, w - 2, step):
            draw.ellipse([x - 1, 3, x + 1, 5], fill=(40, 40, 45, 140))
            draw.ellipse([x - 1, h - 5, x + 1, h - 3], fill=(40, 40, 45, 140))


def _cut_mask(panel, w: int, h: int, px_per_mm: float) -> Image.Image:
    mask = Image.new("L", (w, h), 0)
    mdraw = ImageDraw.Draw(mask)
    if panel.cut_paths:
        poly = [
            (
                int((p.x - panel.x) * px_per_mm),
                int((p.y - panel.y) * px_per_mm),
            )
            for p in panel.cut_paths[0]
        ]
        if len(poly) >= 3:
            mdraw.polygon(poly, fill=255)
        else:
            mdraw.rectangle([0, 0, w, h], fill=255)
    else:
        mdraw.rectangle([0, 0, w, h], fill=255)
    return mask


def _polka(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int) -> None:
    r = max(2, min(w, h) // 9)
    step = r * 3
    for yy in range(y + r, y + h - r, step):
        for xx in range(x + r, x + w - r, step):
            draw.ellipse([xx - r, yy - r, xx + r, yy + r], fill=(245, 245, 245, 255))


def _us_insignia(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    r = max(8, r)
    bar_h = int(r * 0.55)
    bar_w = int(r * 1.45)
    draw.rectangle(
        [cx - bar_w, cy - bar_h // 2, cx + bar_w, cy + bar_h // 2],
        fill=(245, 245, 245, 255),
    )
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(28, 52, 118, 255))
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r * (0.92 if i % 2 == 0 else 0.38)
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    draw.polygon(pts, fill=(245, 245, 245, 255))
    rh = max(2, bar_h // 4)
    draw.rectangle(
        [cx - bar_w, cy - bar_h // 2, cx - r - 1, cy - bar_h // 2 + rh],
        fill=(185, 35, 40, 255),
    )
    draw.rectangle(
        [cx + r + 1, cy - bar_h // 2, cx + bar_w, cy - bar_h // 2 + rh],
        fill=(185, 35, 40, 255),
    )


def _draw_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    size: int,
    fill=(20, 20, 22, 230),
) -> None:
    try:
        font = ImageFont.truetype("/System/Fonts/Helvetica.ttc", size)
    except OSError:
        try:
            font = ImageFont.truetype("/System/Fonts/SFNSMono.ttf", size)
        except OSError:
            font = ImageFont.load_default()
    draw.text((x, y), text, font=font, fill=fill)
