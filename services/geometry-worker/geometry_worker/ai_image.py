"""Opcjonalna generacja bitmap przez lokalne A1111 / ComfyUI.

Bez uruchomionego serwera zwraca None — bake proceduralny zostaje źródłem prawdy.
"""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path

from PIL import Image


def try_generate_panel_image(
    prompt: str,
    width: int,
    height: int,
    negative: str | None = None,
) -> Image.Image | None:
    """Próbuje A1111 (7860) potem ComfyUI nie — tu uproszczone A1111 txt2img."""
    if os.environ.get("AI_IMAGE_ENABLED", "1") in {"0", "false", "False"}:
        return None

    base = os.environ.get("AI_IMAGE_BASE_URL", "http://127.0.0.1:7860").rstrip("/")
    negative = negative or (
        "text, watermark, logo, blurry, low quality, cartoon, plastic toy, "
        "rectangular grid UV, writing, letters, words"
    )

    try:
        import urllib.request
        import json

        payload = json.dumps(
            {
                "prompt": prompt,
                "negative_prompt": negative,
                "width": min(768, max(64, width)),
                "height": min(768, max(64, height)),
                "steps": 20,
                "cfg_scale": 5.5,
                "sampler_name": "DPM++ 2M",
            }
        ).encode()
        req = urllib.request.Request(
            f"{base}/sdapi/v1/txt2img",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        b64 = (data.get("images") or [None])[0]
        if not b64:
            return None
        raw = base64.b64decode(b64.split(",", 1)[-1] if "," in b64 else b64)
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        return img.resize((width, height), Image.Resampling.LANCZOS)
    except Exception:
        return None


def panel_paint_prompt(panel_name: str, scheme_label: str, finish: str) -> str:
    base = (
        f"top-down flat paper model kit texture, {scheme_label}, "
        f"{finish} aircraft aluminum skin, panel lines, rivets, subtle weathering, "
        "orthographic, seamless fill, no text, no labels, high detail"
    )
    if "wing" in panel_name and "upper" in panel_name:
        return base + ", US star and bar insignia, wing planform"
    if "fuse_" in panel_name or "nose" in panel_name:
        return base + ", fuselage skin unwrap, exhaust staining"
    if "canopy" in panel_name:
        return "canopy glass blue tint with dark frame, orthographic, no text"
    if "spinner" in panel_name or "prop" in panel_name:
        return base + ", propeller or spinner segment"
    if "fin" in panel_name or "rudder" in panel_name or "tailplane" in panel_name:
        return base + ", tail surface"
    return base
