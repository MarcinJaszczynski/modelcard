"""Eksport rozwinięcia do PDF (single lub multi-page)."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas

from .box_unfold import Point, UnfoldResult
from .styles import StylePreset, resolve_style
from .svg_export import SHEETS


def _draw_page(
    c: canvas.Canvas,
    result: UnfoldResult,
    sheet: str,
    title: str,
    style: StylePreset,
    page_index: int,
    page_count: int,
    allow_scale: bool,
) -> None:
    sw, sh = SHEETS.get(sheet, SHEETS["A4"])
    scale = 1.0
    if allow_scale and (result.width_mm > sw - 4 or result.height_mm > sh - 4):
        scale = min((sw - 4) / result.width_mm, (sh - 4) / result.height_mm)

    offset_x = (sw - result.width_mm * scale) / 2
    offset_y = max(12.0, (sh - result.height_mm * scale) / 2)

    def tx(p: Point) -> tuple[float, float]:
        x = offset_x + p.x * scale
        y = sh - (offset_y + p.y * scale)
        return x, y

    cut_fill = HexColor(style.cut_fill)
    flap_fill = HexColor(style.flap_fill)
    stroke = HexColor(style.stroke)
    fold = HexColor(style.fold)
    label_fill = HexColor(style.label_fill)

    c.setFillColor(white)
    c.rect(0, 0, sw, sh, fill=1, stroke=0)

    c.setFillColor(label_fill)
    c.setFont("Helvetica-Bold", 4)
    c.drawString(5, sh - 7, title)
    c.setFont("Helvetica", 2.8)
    c.setFillColor(HexColor("#444444"))
    page_note = f" · strona {page_index}/{page_count}" if page_count > 1 else ""
    c.drawString(
        5,
        sh - 11,
        f"Arkusz {sheet}{page_note} · styl: {style.label} · skala {scale:.3f}",
    )

    for panel in result.panels:
        for i, path_pts in enumerate(panel.cut_paths):
            pts = [tx(p) for p in path_pts]
            if len(pts) < 2:
                continue
            path = c.beginPath()
            path.moveTo(pts[0][0], pts[0][1])
            for x, y in pts[1:]:
                path.lineTo(x, y)
            path.close()
            c.setFillColor(cut_fill if i == 0 else flap_fill)
            c.setStrokeColor(stroke)
            c.setLineWidth(0.35)
            c.drawPath(path, fill=1, stroke=1)

        for marking in panel.markings:
            pts = [tx(p) for p in marking.points]
            if len(pts) < 2:
                continue
            path = c.beginPath()
            path.moveTo(pts[0][0], pts[0][1])
            for x, y in pts[1:]:
                path.lineTo(x, y)
            path.close()
            if marking.kind == "window":
                c.setFillColor(HexColor("#cfe8f7"))
            elif marking.kind == "door":
                c.setFillColor(HexColor("#d6c2a4"))
            else:
                c.setFillColor(white)
            c.setStrokeColor(HexColor("#1a3a4a"))
            c.setLineWidth(0.3)
            c.drawPath(path, fill=1, stroke=1)

        c.setDash(1.5, 1.2)
        c.setStrokeColor(fold)
        c.setLineWidth(0.25)
        for a, b in panel.fold_lines:
            x1, y1 = tx(a)
            x2, y2 = tx(b)
            c.line(x1, y1, x2, y2)
        c.setDash()

        cx = offset_x + (panel.x + panel.w / 2) * scale
        cy = sh - (offset_y + (panel.y + panel.h / 2) * scale)
        c.setFillColor(label_fill)
        c.setFont("Helvetica", 3.2)
        c.drawCentredString(cx, cy - 1.1, panel.label)

    iy = 4 + len(result.instructions) * 3.2
    c.setFont("Helvetica", 2.8)
    c.setFillColor(HexColor("#444444"))
    c.drawString(5, iy, "Instrukcja sklejania:")
    for i, line in enumerate(result.instructions):
        c.drawString(5, iy - (i + 1) * 3.2, f"{i + 1}. {line}")


def write_pdf(
    result: UnfoldResult,
    path: Path,
    sheet: str = "A4",
    title: str = "Kartonowy Modelarz",
    style: StylePreset | str | None = "clean",
) -> Path:
    return write_pdf_pages([result], path, sheet=sheet, title=title, style=style)


def write_pdf_pages(
    pages: list[UnfoldResult],
    path: Path,
    sheet: str = "A4",
    title: str = "Kartonowy Modelarz",
    style: StylePreset | str | None = "clean",
    multisheet: bool = False,
) -> Path:
    preset = style if isinstance(style, StylePreset) else resolve_style(style)
    sw, sh = SHEETS.get(sheet, SHEETS["A4"])
    path.parent.mkdir(parents=True, exist_ok=True)

    mm = 2.834645669
    c = canvas.Canvas(str(path), pagesize=(sw * mm, sh * mm))
    c.scale(mm, mm)

    count = len(pages)
    for i, page in enumerate(pages, start=1):
        _draw_page(
            c,
            page,
            sheet,
            title,
            preset,
            i,
            count,
            allow_scale=not multisheet or count == 1,
        )
        c.showPage()
        c.scale(mm, mm)

    c.save()
    return path
