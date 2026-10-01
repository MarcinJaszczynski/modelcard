"""Presety kolorystyczne + defs SVG (weathering, modulacja, hatch)."""

from __future__ import annotations

from dataclasses import dataclass

from .style_recipe import StyleRecipe


@dataclass(frozen=True)
class StylePreset:
    key: str
    label: str
    cut_fill: str
    flap_fill: str
    stroke: str
    fold: str
    label_fill: str
    pattern: str | None = None  # dirt|rust|dust|None
    overlay_opacity: float = 0.0
    # modulacja / zacieki
    fill_light: str | None = None
    fill_dark: str | None = None
    streak_color: str | None = None


PRESETS: dict[str, StylePreset] = {
    "clean": StylePreset(
        key="clean",
        label="Czysty druk",
        cut_fill="#f4efe4",
        flap_fill="#ebe3d2",
        stroke="#111111",
        fold="#333333",
        label_fill="#111111",
        fill_light="#faf7f0",
        fill_dark="#e4dcc8",
        streak_color="#8a7a60",
    ),
    "dirt": StylePreset(
        key="dirt",
        label="Lekki brud",
        cut_fill="#e4d9bf",
        flap_fill="#d8cbae",
        stroke="#1a1510",
        fold="#3a3228",
        label_fill="#1a1510",
        pattern="dirt",
        overlay_opacity=0.16,
        fill_light="#efe4cb",
        fill_dark="#cfc0a0",
        streak_color="#5c4a32",
    ),
    "rust": StylePreset(
        key="rust",
        label="Rdza",
        cut_fill="#d4b892",
        flap_fill="#c4a57a",
        stroke="#2a1810",
        fold="#5a3a28",
        label_fill="#2a1810",
        pattern="rust",
        overlay_opacity=0.2,
        fill_light="#e0c49e",
        fill_dark="#b8895c",
        streak_color="#8a3a18",
    ),
    "dust": StylePreset(
        key="dust",
        label="Kurz / pył",
        cut_fill="#e8e2d2",
        flap_fill="#ddd6c4",
        stroke="#222222",
        fold="#555555",
        label_fill="#222222",
        pattern="dust",
        overlay_opacity=0.14,
        fill_light="#f0ebe0",
        fill_dark="#d2cbb8",
        streak_color="#7a7568",
    ),
}


def resolve_style(key: str | None) -> StylePreset:
    if not key:
        return PRESETS["clean"]
    return PRESETS.get(str(key).lower(), PRESETS["clean"])


def svg_defs_for_style(style: StylePreset, recipe: StyleRecipe | None = None) -> list[str]:
    recipe = recipe or StyleRecipe()
    light = style.fill_light or style.cut_fill
    dark = style.fill_dark or style.cut_fill
    streak = style.streak_color or "#666666"

    lines = [
        '  <style type="text/css"><![CDATA[',
        f"    .cut {{ fill: {style.cut_fill}; stroke: {style.stroke}; stroke-width: 0.4; }}",
        f"    .cut-mod {{ stroke: {style.stroke}; stroke-width: 0.4; }}",
        f"    .bleed {{ fill: {dark}; stroke: none; }}",
        f"    .flap {{ fill: {style.flap_fill}; stroke: {style.stroke}; stroke-width: 0.35; }}",
        f"    .fold {{ fill: none; stroke: {style.fold}; stroke-width: 0.28; stroke-dasharray: 1.6 1.1; }}",
        f"    .panel-line {{ fill: none; stroke: {style.stroke}; stroke-width: 0.18; stroke-opacity: 0.45; }}",
        f"    .rivet {{ fill: none; stroke: {style.stroke}; stroke-width: 0.2; stroke-opacity: 0.55; }}",
        f"    .edge-shade {{ fill: none; stroke: {dark}; stroke-width: 1.2; stroke-opacity: 0.22; }}",
        f"    .label {{ font-family: Helvetica, Arial, sans-serif; font-size: 2.8px; fill: {style.label_fill}; text-anchor: middle; opacity: 0.75; }}",
        f"    .part-no {{ font-family: Helvetica, Arial, sans-serif; font-size: 3.4px; font-weight: bold; fill: {style.label_fill}; text-anchor: middle; }}",
        "    .part-badge { fill: #fff; stroke: #111; stroke-width: 0.25; fill-opacity: 0.92; }",
        "    .meta { font-family: Helvetica, Arial, sans-serif; font-size: 2.6px; fill: #444; }",
        f"    .title {{ font-family: Helvetica, Arial, sans-serif; font-size: 4px; fill: {style.label_fill}; font-weight: bold; }}",
        "    .weather { pointer-events: none; mix-blend-mode: multiply; }",
        f"    .streak {{ fill: none; stroke: {streak}; stroke-width: 0.35; stroke-opacity: 0.35; stroke-linecap: round; }}",
        f"    .glue {{ fill: none; stroke: {style.fold}; stroke-width: 0.15; stroke-opacity: 0.35; }}",
        "    .mark-window { fill: #b9d7ea; stroke: #1a3a4a; stroke-width: 0.28; }",
        "    .mark-door { fill: #cbb59a; stroke: #3a2a18; stroke-width: 0.32; }",
        "    .mark-detail { fill: none; stroke: #444; stroke-width: 0.25; }",
        "  ]]></style>",
    ]

    if recipe.color_modulation:
        lines += [
            '  <linearGradient id="panelMod" x1="0" y1="0" x2="0" y2="1">',
            f'    <stop offset="0%" stop-color="{light}"/>',
            f'    <stop offset="100%" stop-color="{dark}"/>',
            "  </linearGradient>",
        ]

    if style.pattern == "dirt":
        lines += [
            '  <pattern id="weatherPattern" patternUnits="userSpaceOnUse" width="9" height="9">',
            f'    <circle cx="1.5" cy="2" r="0.55" fill="#6b5a40" fill-opacity="{style.overlay_opacity}"/>',
            f'    <circle cx="5.5" cy="6" r="0.8" fill="#5a4a35" fill-opacity="{style.overlay_opacity * 0.75}"/>',
            f'    <circle cx="7" cy="1.8" r="0.4" fill="#7a6a50" fill-opacity="{style.overlay_opacity}"/>',
            "  </pattern>",
        ]
    elif style.pattern == "rust":
        lines += [
            '  <pattern id="weatherPattern" patternUnits="userSpaceOnUse" width="11" height="11">',
            f'    <ellipse cx="3" cy="4" rx="2" ry="1.3" fill="#a05028" fill-opacity="{style.overlay_opacity}"/>',
            f'    <ellipse cx="8" cy="7.5" rx="1.5" ry="1.8" fill="#8a3a18" fill-opacity="{style.overlay_opacity * 0.85}"/>',
            f'    <circle cx="8.5" cy="2.2" r="1" fill="#b86830" fill-opacity="{style.overlay_opacity * 0.65}"/>',
            "  </pattern>",
        ]
    elif style.pattern == "dust":
        lines += [
            '  <pattern id="weatherPattern" patternUnits="userSpaceOnUse" width="6" height="6">',
            f'    <circle cx="1" cy="1" r="0.3" fill="#888070" fill-opacity="{style.overlay_opacity}"/>',
            f'    <circle cx="4" cy="3.2" r="0.22" fill="#9a9080" fill-opacity="{style.overlay_opacity}"/>',
            f'    <circle cx="2.4" cy="5" r="0.28" fill="#7a7568" fill-opacity="{style.overlay_opacity}"/>',
            "  </pattern>",
        ]

    lines += [
        '  <pattern id="glueHatch" patternUnits="userSpaceOnUse" width="3" height="3">',
        '    <path d="M0,3 L3,0" stroke="#666" stroke-width="0.2" stroke-opacity="0.35"/>',
        "  </pattern>",
    ]

    return lines
