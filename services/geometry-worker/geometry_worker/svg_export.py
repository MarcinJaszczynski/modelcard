"""Eksport rozwinięcia do SVG — wygląd wycinanki (bleed, linie, numery, weathering)."""

from __future__ import annotations

import math
from pathlib import Path

from .box_unfold import FacePanel, Point, UnfoldResult
from .style_recipe import StyleRecipe
from .styles import StylePreset, resolve_style, svg_defs_for_style

SHEETS = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
}


def _poly_points(points: list[Point]) -> str:
    return " ".join(f"{p.x:.3f},{p.y:.3f}" for p in points)


def _poly_to_path_d(points: list[Point]) -> str:
    if not points:
        return ""
    bits = [f"M {points[0].x:.3f},{points[0].y:.3f}"]
    for p in points[1:]:
        bits.append(f"L {p.x:.3f},{p.y:.3f}")
    bits.append("Z")
    return " ".join(bits)


def _polygon_area(pts: list[Point]) -> float:
    n = len(pts)
    if n < 3:
        return 0.0
    return 0.5 * sum(
        pts[i].x * pts[(i + 1) % n].y - pts[(i + 1) % n].x * pts[i].y for i in range(n)
    )


def _expand_polygon(pts: list[Point], bleed: float) -> list[Point]:
    """Offset wielokąta na zewnątrz (aproksymacja wierzchołkowa)."""
    n = len(pts)
    if n < 3 or bleed <= 0:
        return list(pts)
    ccw = _polygon_area(pts) >= 0
    out: list[Point] = []
    for i in range(n):
        prev = pts[(i - 1) % n]
        curr = pts[i]
        nxt = pts[(i + 1) % n]

        def _norm(a: Point, b: Point) -> tuple[float, float]:
            dx, dy = b.x - a.x, b.y - a.y
            length = math.hypot(dx, dy) or 1.0
            # normalna na zewnątrz: CCW → prawo od krawędzi; CW → lewo
            nx, ny = dy / length, -dx / length
            if not ccw:
                nx, ny = -nx, -ny
            return nx, ny

        n1x, n1y = _norm(prev, curr)
        n2x, n2y = _norm(curr, nxt)
        mx, my = n1x + n2x, n1y + n2y
        ml = math.hypot(mx, my) or 1.0
        out.append(Point(curr.x + bleed * mx / ml, curr.y + bleed * my / ml))
    return out


def _centroid(pts: list[Point]) -> Point:
    if not pts:
        return Point(0.0, 0.0)
    return Point(sum(p.x for p in pts) / len(pts), sum(p.y for p in pts) / len(pts))


def _point_in_poly(x: float, y: float, pts: list[Point]) -> bool:
    """Ray casting."""
    n = len(pts)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = pts[i].x, pts[i].y
        xj, yj = pts[j].x, pts[j].y
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


def _sample_edge(a: Point, b: Point, step: float) -> list[Point]:
    dist = math.hypot(b.x - a.x, b.y - a.y)
    if dist < 1e-6:
        return []
    n = max(1, int(dist / step))
    return [
        Point(a.x + (b.x - a.x) * (i + 0.5) / n, a.y + (b.y - a.y) * (i + 0.5) / n)
        for i in range(n)
    ]


def _inset_point(p: Point, pts: list[Point], inset: float) -> Point:
    c = _centroid(pts)
    dx, dy = c.x - p.x, c.y - p.y
    L = math.hypot(dx, dy) or 1.0
    return Point(p.x + inset * dx / L, p.y + inset * dy / L)


def _is_skeleton(name: str) -> bool:
    return name.startswith(("former_", "rib_", "spar_")) or name == "keel"


def _panel_detail_lines(
    panel: FacePanel,
    recipe: StyleRecipe,
) -> list[str]:
    """Linie podziału + nity wzdłuż obrysu cut (nie po bbox). Szkielet bez nitów."""
    out: list[str] = []
    if _is_skeleton(panel.name):
        return out
    if not panel.cut_paths:
        return out
    outline = panel.cut_paths[0]
    if len(outline) < 3:
        return out

    if recipe.panel_lines:
        spacing = max(6.0, recipe.panel_line_spacing_mm)
        minx = min(p.x for p in outline)
        maxx = max(p.x for p in outline)
        miny = min(p.y for p in outline)
        maxy = max(p.y for p in outline)
        # linie chord-wise (poziome w bbox) przycięte do wielokąta
        y = miny + spacing
        while y < maxy - 1.5:
            hits: list[float] = []
            for i in range(len(outline)):
                a, b = outline[i], outline[(i + 1) % len(outline)]
                if (a.y <= y <= b.y) or (b.y <= y <= a.y):
                    if abs(b.y - a.y) < 1e-9:
                        continue
                    t = (y - a.y) / (b.y - a.y)
                    if 0 <= t <= 1:
                        hits.append(a.x + t * (b.x - a.x))
            hits = sorted(set(round(h, 3) for h in hits))
            for i in range(0, len(hits) - 1, 2):
                x0, x1 = hits[i], hits[i + 1]
                if x1 - x0 > 3:
                    out.append(
                        f'  <line class="panel-line" x1="{x0 + 1.2:.3f}" y1="{y:.3f}" '
                        f'x2="{x1 - 1.2:.3f}" y2="{y:.3f}"/>'
                    )
            y += spacing

        # fuga wzdłuż rozpiętości (środek bbox, tylko gdy wewnątrz)
        mid = (minx + maxx) / 2
        if maxx - minx > 40 and _point_in_poly(mid, (miny + maxy) / 2, outline):
            ys = []
            for i in range(len(outline)):
                a, b = outline[i], outline[(i + 1) % len(outline)]
                if (a.x <= mid <= b.x) or (b.x <= mid <= a.x):
                    if abs(b.x - a.x) < 1e-9:
                        continue
                    t = (mid - a.x) / (b.x - a.x)
                    if 0 <= t <= 1:
                        ys.append(a.y + t * (b.y - a.y))
            ys = sorted(ys)
            if len(ys) >= 2:
                out.append(
                    f'  <line class="panel-line" x1="{mid:.3f}" y1="{ys[0] + 1.5:.3f}" '
                    f'x2="{mid:.3f}" y2="{ys[-1] - 1.5:.3f}"/>'
                )

    if recipe.rivets:
        step = max(4.0, recipe.rivet_spacing_mm)
        r = 0.55
        for i in range(len(outline)):
            a, b = outline[i], outline[(i + 1) % len(outline)]
            for p in _sample_edge(a, b, step):
                ip = _inset_point(p, outline, 1.4)
                if _point_in_poly(ip.x, ip.y, outline):
                    out.append(
                        f'  <circle class="rivet" cx="{ip.x:.3f}" cy="{ip.y:.3f}" r="{r}"/>'
                    )

    if recipe.weathering_streaks:
        c = _centroid(outline)
        minx = min(p.x for p in outline)
        maxx = max(p.x for p in outline)
        miny = min(p.y for p in outline)
        n = max(2, int((maxx - minx) / 22))
        for i in range(n):
            sx = minx + (i + 0.6) * (maxx - minx) / n
            # start blisko górnej krawędzi wewnątrz
            start = Point(sx, miny + 2)
            for _ in range(12):
                if _point_in_poly(start.x, start.y, outline):
                    break
                start = Point(start.x, start.y + 1.5)
            if not _point_in_poly(start.x, start.y, outline):
                continue
            length = min((c.y - miny) * 0.9, 18 + (i % 3) * 4)
            out.append(
                f'  <line class="streak" x1="{start.x:.3f}" y1="{start.y:.3f}" '
                f'x2="{start.x + 0.4:.3f}" y2="{start.y + length:.3f}"/>'
            )

    return out


def render_svg(
    result: UnfoldResult,
    sheet: str = "A4",
    title: str = "Kartonowy Modelarz",
    style: StylePreset | str | None = "clean",
    page_index: int = 1,
    page_count: int = 1,
    allow_scale: bool = True,
    recipe: StyleRecipe | None = None,
    textures: dict[str, Path] | None = None,
) -> str:
    preset = style if isinstance(style, StylePreset) else resolve_style(style)
    recipe = recipe or StyleRecipe()
    textures = textures or {}
    sw, sh = SHEETS.get(sheet, SHEETS["A4"])

    scale = 1.0
    if allow_scale and (result.width_mm > sw - 4 or result.height_mm > sh - 4):
        scale = min((sw - 4) / result.width_mm, (sh - 4) / result.height_mm)

    offset_x = (sw - result.width_mm * scale) / 2
    offset_y = max(12.0, (sh - result.height_mm * scale) / 2)

    def tx(p: Point) -> Point:
        return Point(offset_x + p.x * scale, offset_y + p.y * scale)

    def transform_panel(panel: FacePanel) -> FacePanel:
        from .box_unfold import Marking

        return FacePanel(
            id=panel.id,
            name=panel.name,
            label=panel.label,
            x=offset_x + panel.x * scale,
            y=offset_y + panel.y * scale,
            w=panel.w * scale,
            h=panel.h * scale,
            flaps=[[tx(p) for p in flap] for flap in panel.flaps],
            fold_lines=[(tx(a), tx(b)) for a, b in panel.fold_lines],
            cut_paths=[[tx(p) for p in path] for path in panel.cut_paths],
            markings=[
                Marking(kind=m.kind, points=[tx(p) for p in m.points])
                for m in panel.markings
            ],
        )

    panels = [transform_panel(p) for p in result.panels]
    page_note = f" · strona {page_index}/{page_count}" if page_count > 1 else ""
    recipe_scaled = StyleRecipe(
        profile=recipe.profile,
        bleed_mm=recipe.bleed_mm * scale,
        panel_lines=recipe.panel_lines,
        panel_line_spacing_mm=recipe.panel_line_spacing_mm * scale,
        rivets=recipe.rivets,
        rivet_spacing_mm=recipe.rivet_spacing_mm * scale,
        color_modulation=recipe.color_modulation,
        weathering_streaks=recipe.weathering_streaks,
        part_numbers=recipe.part_numbers,
        glue_hatch=recipe.glue_hatch,
        edge_darken=recipe.edge_darken,
        show_part_labels=recipe.show_part_labels,
    )

    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{sw}mm" height="{sh}mm" viewBox="0 0 {sw} {sh}">',
        f"<title>{_escape(title)}</title>",
        "<defs>",
        *svg_defs_for_style(preset, recipe_scaled),
    ]

    for panel in panels:
        if panel.name not in textures or not panel.cut_paths:
            continue
        # clip = prawdziwy obrys cut, nie bbox — inaczej bitmapa robi „prostokąty”
        parts.append(
            f'  <clipPath id="clip-{_escape(panel.id)}">'
            f'<polygon points="{_poly_points(panel.cut_paths[0])}"/>'
            f"</clipPath>"
        )

    parts += [
        "</defs>",
        f'<rect x="0" y="0" width="{sw}" height="{sh}" fill="#fafafa"/>',
        f'<text x="5" y="7" class="title">{_escape(title)}</text>',
        f'<text x="5" y="11" class="meta">Arkusz {sheet}{page_note} · profil: {recipe.profile} · '
        f"styl: {preset.label} · cut/fold · skala {scale:.3f}"
        f"{' · bitmapy' if textures else ''}</text>",
    ]

    for idx, panel in enumerate(panels, start=1):
        parts.append(f'<g id="part-{panel.id}" data-name="{panel.name}">')
        main = panel.cut_paths[0] if panel.cut_paths else []
        skeleton = _is_skeleton(panel.name)

        # bleed tylko na skórach — na wręgach robi „kwadratowe koła”
        if (not skeleton) and recipe_scaled.bleed_mm > 0 and len(main) >= 3:
            bleed_pts = _expand_polygon(main, recipe_scaled.bleed_mm)
            parts.append(
                f'  <polygon class="bleed" points="{_poly_points(bleed_pts)}"/>'
            )

        tex = textures.get(panel.name)
        holes = panel.cut_paths[1:] if skeleton and len(panel.cut_paths) > 1 else []
        skin_extras = [] if skeleton else panel.cut_paths[1:]

        if skeleton and main:
            # jeden path z otworami (evenodd) — czysta wręga
            d_parts = [_poly_to_path_d(main)] + [_poly_to_path_d(h) for h in holes]
            d = " ".join(d_parts)
            fill = "url(#panelMod)" if recipe_scaled.color_modulation else "#f4efe4"
            parts.append(
                f'  <path class="cut-mod" fill="{fill}" fill-rule="evenodd" d="{d}"/>'
            )
            for a, b in panel.fold_lines:
                parts.append(
                    f'  <line class="fold" x1="{a.x:.3f}" y1="{a.y:.3f}" '
                    f'x2="{b.x:.3f}" y2="{b.y:.3f}"/>'
                )
        else:
            for i, path in enumerate(panel.cut_paths):
                if i == 0:
                    if tex is not None:
                        href = Path(tex).name
                        parts.append(
                            f'  <image href="{_escape(href)}" xlink:href="{_escape(href)}" '
                            f'x="{panel.x:.3f}" y="{panel.y:.3f}" '
                            f'width="{panel.w:.3f}" height="{panel.h:.3f}" '
                            f'preserveAspectRatio="none" clip-path="url(#clip-{_escape(panel.id)})"/>'
                        )
                        parts.append(
                            f'  <polygon class="cut-mod" fill="none" '
                            f'points="{_poly_points(path)}"/>'
                        )
                    elif recipe_scaled.color_modulation:
                        parts.append(
                            f'  <polygon class="cut-mod" fill="url(#panelMod)" '
                            f'points="{_poly_points(path)}"/>'
                        )
                    else:
                        parts.append(
                            f'  <polygon class="cut" points="{_poly_points(path)}"/>'
                        )
                    if recipe_scaled.edge_darken:
                        parts.append(
                            f'  <polygon class="edge-shade" points="{_poly_points(path)}"/>'
                        )
                    if preset.pattern and tex is None:
                        parts.append(
                            f'  <polygon class="weather" fill="url(#weatherPattern)" '
                            f'points="{_poly_points(path)}"/>'
                        )
                else:
                    parts.append(
                        f'  <polygon class="flap" points="{_poly_points(path)}"/>'
                    )
                    if recipe_scaled.glue_hatch:
                        parts.append(
                            f'  <polygon fill="url(#glueHatch)" stroke="none" '
                            f'points="{_poly_points(path)}"/>'
                        )

        if not skeleton:
            parts.extend(_panel_detail_lines(panel, recipe_scaled))

        for marking in panel.markings:
            cls = {
                "window": "mark-window",
                "door": "mark-door",
            }.get(marking.kind, "mark-detail")
            parts.append(
                f'  <polygon class="{cls}" points="{_poly_points(marking.points)}"/>'
            )

        if not skeleton:
            for a, b in panel.fold_lines:
                parts.append(
                    f'  <line class="fold" x1="{a.x:.3f}" y1="{a.y:.3f}" '
                    f'x2="{b.x:.3f}" y2="{b.y:.3f}"/>'
                )

        c = _centroid(main) if main else Point(panel.x + panel.w / 2, panel.y + panel.h / 2)

        # Jak w prawdziwej wycinance: tylko numer części — bez nazw na farbie.
        show_name_labels = recipe.show_part_labels and not textures

        if recipe_scaled.part_numbers and main:
            # numer POZA obrysem cut (jak na planszach Halińskiego) — nad lewym rogiem bbox
            minx = min(p.x for p in main)
            miny = min(p.y for p in main)
            bx = minx + 2.2
            by = max(3.5, miny - 3.2)
            parts.append(
                f'  <text class="part-no" x="{bx:.3f}" y="{by:.3f}">{idx}</text>'
            )

        if show_name_labels:
            parts.append(
                f'  <text class="label" x="{c.x:.3f}" y="{c.y:.3f}">{_escape(panel.label)}</text>'
            )
        parts.append("</g>")

    legend_y = sh - 6
    parts.append(
        f'<text x="5" y="{legend_y:.3f}" class="meta">'
        "Legenda: ciągła=cięcie · przerywana=gięcie · kropki=nity · "
        f"spad bleed={recipe.bleed_mm:g} mm · profil {recipe.profile}"
        f"{' · ★podklej=część poniżej min. wymiaru' if any('podklej' in p.label for p in panels) else ''}"
        "</text>"
    )

    parts.append("</svg>")
    return "\n".join(parts)


def write_svg(
    result: UnfoldResult,
    path: Path,
    sheet: str = "A4",
    title: str = "",
    style: str | StylePreset | None = "clean",
    page_index: int = 1,
    page_count: int = 1,
    allow_scale: bool = True,
    recipe: StyleRecipe | None = None,
    textures: dict[str, Path] | None = None,
) -> Path:
    import shutil

    path.parent.mkdir(parents=True, exist_ok=True)
    local_textures: dict[str, Path] = {}
    if textures:
        for name, src in textures.items():
            src = Path(src)
            if not src.exists():
                continue
            dest = path.parent / src.name
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
            local_textures[name] = dest

    svg = render_svg(
        result,
        sheet=sheet,
        title=title or "Kartonowy Modelarz",
        style=style,
        page_index=page_index,
        page_count=page_count,
        allow_scale=allow_scale,
        recipe=recipe,
        textures=local_textures or None,
    )
    path.write_text(svg, encoding="utf-8")
    return path


def write_svg_pages(
    pages: list[UnfoldResult],
    output_dir: Path,
    sheet: str = "A4",
    title: str = "",
    style: str | StylePreset | None = "clean",
    multisheet: bool = False,
    basename: str = "sheet",
    recipe: StyleRecipe | None = None,
    textures: dict[str, Path] | None = None,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    count = len(pages)
    for i, page in enumerate(pages, start=1):
        name = f"{basename}.svg" if count == 1 else f"{basename}_{i:02d}.svg"
        page_tex = None
        if textures:
            names = {p.name for p in page.panels}
            page_tex = {k: v for k, v in textures.items() if k in names} or None
        paths.append(
            write_svg(
                page,
                output_dir / name,
                sheet=sheet,
                title=title,
                style=style,
                page_index=i,
                page_count=count,
                allow_scale=not multisheet or count == 1,
                recipe=recipe,
                textures=page_tex,
            )
        )
    return paths


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
