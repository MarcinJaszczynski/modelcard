"""Arkusze PDF: wektorowo, zawsze 1 mm bryły = 1 mm na papierze."""
from __future__ import annotations

import math
from pathlib import Path

import shapely
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from .layout import FOOTER, MARGIN, PAGES
from .project import Project
from .validate import Check

FONT_CANDIDATES = [
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
]
FONT, BOLD = "Modelarz", "Modelarz-Bold"
RULER_MM = 100.0
RULER_Y = MARGIN + 2.0   # dolna krawędź paska kontrolnego [mm]

DASH = {"mountain": [5, 1.5, 0.8, 1.5], "valley": [2.5, 1.8], "glue": [0.6, 1.2]}
SEAM_COLOR = HexColor("#143a8a")
CUT_COLOR = HexColor("#c0261a")


def find_fonts() -> tuple[str, str]:
    for reg, bold in FONT_CANDIDATES:
        if Path(reg).exists():
            return reg, bold if Path(bold).exists() else reg
    raise RuntimeError("Nie znaleziono fontu TrueType z polskimi znakami (Arial / DejaVu Sans / Liberation Sans)")


def _fonts():
    if FONT not in pdfmetrics.getRegisteredFontNames():
        reg, bold = find_fonts()
        pdfmetrics.registerFont(TTFont(FONT, reg))
        pdfmetrics.registerFont(TTFont(BOLD, bold))


def _path(c: Canvas, pts, close=True):
    p = c.beginPath()
    p.moveTo(pts[0][0] * mm, pts[0][1] * mm)
    for q in pts[1:]:
        p.lineTo(q[0] * mm, q[1] * mm)
    if close:
        p.close()
    return p


def _line(c: Canvas, a, b):
    c.line(a[0] * mm, a[1] * mm, b[0] * mm, b[1] * mm)


def _frame(c: Canvas, pr: Project, idx: int, total: int, group: str):
    w, h = PAGES[pr.page]
    c.setFillColor(black)
    right = f"{group}   ·   strona {idx}/{total}   ·   skala 1:1"
    room = (w - 2 * MARGIN) * mm - pdfmetrics.stringWidth(right, FONT, 8) - 12
    size = min(9.0, 9.0 * room / max(1.0, pdfmetrics.stringWidth(pr.model.title, BOLD, 9)))
    c.setFont(BOLD, size)
    c.drawString(MARGIN * mm, (h - MARGIN - 4) * mm, pr.model.title)
    c.setFont(FONT, 8)
    c.drawRightString((w - MARGIN) * mm, (h - MARGIN - 4) * mm, right)
    c.setLineWidth(0.3)
    c.setStrokeColor(black)
    c.line(MARGIN * mm, (h - MARGIN - 6) * mm, (w - MARGIN) * mm, (h - MARGIN - 6) * mm)
    c.line(MARGIN * mm, (MARGIN + FOOTER - 2) * mm, (w - MARGIN) * mm, (MARGIN + FOOTER - 2) * mm)
    # podziałka kontrolna
    c.rect(MARGIN * mm, RULER_Y * mm, RULER_MM * mm, 1.0 * mm, stroke=0, fill=1)
    c.setFont(FONT, 5.5)
    for t in range(0, int(RULER_MM) + 1, 10):
        x = MARGIN + t
        c.line(x * mm, (RULER_Y + 1) * mm, x * mm, (RULER_Y + (3 if t % 50 == 0 else 2)) * mm)
        if t % 50 == 0:
            c.drawCentredString(x * mm, (RULER_Y + 3.6) * mm, f"{t}")
    c.setFont(FONT, 6)
    c.drawString(MARGIN * mm, (RULER_Y + 7.2) * mm,
                 "Kontrola wydruku: czarny pasek ma dokładnie 100 mm. Drukuj w skali 100% (bez dopasowania do strony).")
    # legenda
    lx = MARGIN + RULER_MM + 8
    rows = [("cięcie", None, black), ("zgięcie od siebie (grzbiet)", DASH["mountain"], black),
            ("zgięcie do siebie (dolina)", DASH["valley"], black), ("obrys miejsca klejenia", DASH["glue"], black),
            ("otwór do wycięcia", None, CUT_COLOR)]
    for i, (txt, dash, col) in enumerate(rows):
        x = lx + (i // 3) * 42
        y = RULER_Y + 5.6 - (i % 3) * 2.8
        c.setStrokeColor(col)
        c.setLineWidth(0.5)
        c.setDash(dash or [])
        c.line(x * mm, y * mm, (x + 9) * mm, y * mm)
        c.setDash([])
        c.setFillColor(black)
        c.drawString((x + 10.5) * mm, (y - 0.7) * mm, txt)
    c.setStrokeColor(black)


def _label_spot(poly):
    try:
        ln = shapely.maximum_inscribed_circle(poly, tolerance=0.2)
        (cx, cy), (bx, by) = ln.coords
        return (cx, cy), ((cx - bx) ** 2 + (cy - by) ** 2) ** 0.5
    except Exception:
        p = poly.representative_point()
        return (p.x, p.y), 2.0


def _badge(c: Canvas, T, badge, text):
    """Numer części obok części, z odnośnikiem do krawędzi."""
    at, anchor = T([badge[0]])[0], T([badge[1]])[0]
    c.setStrokeColor(black)
    c.setLineWidth(0.25)
    c.setDash([])
    dx, dy = anchor[0] - at[0], anchor[1] - at[1]
    ln = max((dx * dx + dy * dy) ** 0.5, 1e-9)
    _line(c, (at[0] + dx / ln * 1.5, at[1] + dy / ln * 1.5), anchor)
    c.setFillColor(black)
    size = 7.5 if len(text) <= 2 else 6.0
    c.setFont(BOLD, size)
    c.drawCentredString(at[0] * mm, at[1] * mm - size * 0.35, text)


def _draw_skin(c: Canvas, pr: Project, it):
    mesh, pc, T = pr.model.mesh, it.ref, it.placement.apply
    part = mesh.parts[pc.part]
    for pf in pc.faces:
        col = HexColor(mesh.faces[pf.face].color or part.color)
        c.setFillColor(col)
        c.setStrokeColor(col)
        c.setLineWidth(0.25)
        c.drawPath(_path(c, T(pf.pts)), stroke=1, fill=1)
    for pts, color, alpha in pc.paint:
        col = HexColor(color)
        c.setFillColor(col)
        c.setStrokeColor(col)
        c.setFillAlpha(alpha)
        c.setLineWidth(0.25)
        c.drawPath(_path(c, T(pts[:-1])), stroke=1 if alpha > 0.99 else 0, fill=1)
    c.setFillAlpha(1)
    c.setLineJoin(1)
    for pts, color, width, alpha, dash in pc.paint_lines:
        c.setStrokeColor(HexColor(color))
        c.setStrokeAlpha(alpha)
        c.setLineWidth(width)
        c.setLineCap(1 if dash else 0)
        c.setDash(list(dash) if dash else [])
        c.drawPath(_path(c, T(pts), close=False), stroke=1, fill=0)
    c.setStrokeAlpha(1)
    c.setLineCap(0)
    c.setDash([])
    c.setStrokeColor(black)
    c.setFillColor(white)
    c.setLineWidth(0.45)
    for poly, *_ in pc.tabs:
        pts = T(list(poly.exterior.coords)[:4])
        c.drawPath(_path(c, pts), stroke=0, fill=1)
        c.drawPath(_path(c, [pts[1], pts[2], pts[3], pts[0]], close=False), stroke=1, fill=0)
    for be in pc.boundary:
        a, b = T([be.a, be.b])
        if be.tabbed:
            c.setLineWidth(0.35)
            c.setDash(DASH["mountain"])
        else:
            c.setLineWidth(0.45)
            c.setDash([])
        _line(c, a, b)
    c.setLineWidth(0.35)
    for f in pc.folds:
        if f.draw:
            c.setDash(DASH[f.kind])
            _line(c, *T([f.a, f.b]))
    for style, label, segs in pc.marks:
        cut = style == "cut"
        c.setStrokeColor(CUT_COLOR if cut else HexColor("#333333"))
        c.setDash([] if cut else DASH["glue"])
        c.setLineWidth(0.4 if cut else 0.35)
        pts = []
        for sg in segs:
            q = T(sg)
            pts += list(q)
            c.drawPath(_path(c, q, close=False), stroke=1, fill=0)
        cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        c.setFillColor(CUT_COLOR if cut else HexColor("#333333"))
        c.setFont(FONT, 4.5)
        c.drawCentredString(cx * mm, (cy - (2.2 if cut else 0.6)) * mm, label)
    c.setDash([])
    c.setStrokeColor(black)
    c.setFillColor(SEAM_COLOR)
    c.setFont(BOLD, 5.5)
    for num, at in pc.seam_labels:
        x, y = T([at])[0]
        c.drawCentredString(x * mm, y * mm - 2, str(num))
    for face, M, text, size, color, x, y in pc.paint_text:
        c.saveState()
        c.clipPath(_path(c, T(face)), stroke=0, fill=0)
        c.scale(mm, mm)
        a = math.radians(it.placement.angle)
        c.transform(math.cos(a), math.sin(a), -math.sin(a), math.cos(a), it.placement.tx, it.placement.ty)
        c.transform(*M)
        c.setFillColor(HexColor(color))
        c.setFont(BOLD, size)
        c.drawCentredString(x, y - 0.35 * size, text)
        c.restoreState()
    _badge(c, T, pc.badge, it.label)


def _draw_plate(c: Canvas, pr: Project, it):
    T = it.placement.apply
    c.setFillColor(HexColor("#f1e6c8"))
    c.setStrokeColor(black)
    c.setLineWidth(0.45)
    c.drawPath(_path(c, T(list(it.outline.exterior.coords)[:-1])), stroke=1, fill=1)
    at, r = _label_spot(it.outline)
    x, y = T([at])[0]
    size = max(4.0, min(8.0, r * 1.6))
    c.setFillColor(black)
    c.setFont(BOLD, size)
    c.drawCentredString(x * mm, y * mm - size * 0.35, it.label)


def _draw_flat(c: Canvas, pr: Project, it):
    fp, T = it.ref, it.placement.apply
    c.setFillColor(HexColor(fp.color))
    c.setStrokeColor(black)
    c.setLineWidth(0.45)
    c.drawPath(_path(c, T(list(fp.poly.exterior.coords)[:-1])), stroke=1, fill=1)
    for g, color in fp.fills:
        for q in getattr(g, "geoms", [g]):
            if q.geom_type == "Polygon" and not q.is_empty:
                c.setFillColor(HexColor(color))
                c.drawPath(_path(c, T(list(q.exterior.coords)[:-1])), stroke=0, fill=1)
    c.setStrokeColor(HexColor("#bbbbbb"))
    c.setLineWidth(0.35)
    c.setDash(DASH["mountain"])
    for a, b in fp.folds:
        _line(c, *T([a, b]))
    c.setDash([])
    _badge(c, T, fp.badge, it.label)


def write_pdf(pr: Project, path, checks: list[Check] | None = None) -> None:
    _fonts()
    w, h = PAGES[pr.page]
    c = Canvas(str(path), pagesize=(w * mm, h * mm), pageCompression=1)
    c.setTitle(pr.model.title)
    c.setAuthor("Modelarz")
    info = _info_lines(pr, checks)
    usable = h - 2 * MARGIN - FOOTER - 14
    info_pages = max(1, -(-sum(hh for *_, hh in info) // usable))
    total = len(pr.sheets) + int(info_pages)
    for pg, (group, _, _) in enumerate(pr.sheets):
        _frame(c, pr, pg + 1, total, group)
        for it in pr.items:
            if it.placement.page == pg:
                {"skin": _draw_skin, "plate": _draw_plate, "flat": _draw_flat}[it.kind](c, pr, it)
        c.showPage()
    # instrukcja
    page_no = len(pr.sheets) + 1
    _frame(c, pr, page_no, total, "Instrukcja montażu")
    y = h - MARGIN - 12
    for font, size, text, hh in info:
        if y - hh < MARGIN + FOOTER + 2:
            c.showPage()
            page_no += 1
            _frame(c, pr, page_no, total, "Instrukcja montażu")
            y = h - MARGIN - 12
        y -= hh
        c.setFillColor(black)
        c.setFont(font, size)
        c.drawString(MARGIN * mm, y * mm, text)
    c.showPage()
    c.save()


def _info_lines(pr: Project, checks):
    """[(font, rozmiar, tekst, wysokość wiersza w mm)]"""
    w = (PAGES[pr.page][0] - 2 * MARGIN) * mm
    out = []

    def head(t):
        out.append((BOLD, 10, t, 8.0))

    def para(t, size=8):
        for ln in simpleSplit(t, FONT, size, w):
            out.append((FONT, size, ln, size * 0.45))
        out.append((FONT, size, "", 1.0))

    head("Jak czytać arkusze")
    para("Wszystkie części są w skali 1:1 względem bryły modelu — przed wycinaniem zmierz czarny pasek kontrolny "
         "u dołu strony. Niebieskie numery przy krawędziach oznaczają szwy: krawędzie z tym samym numerem sklejasz "
         "ze sobą. Biała zakładka jest zawsze tylko po jednej stronie szwu i wchodzi pod drugą część. "
         "Części bez linii zgięć na powierzchni to elementy zwijane (walce, stożki, poszycie).")
    if pr.model.notes:
        head("Uwagi do modelu")
        for i, t in enumerate(pr.model.notes, 1):
            para(f"{i}. {t}")
    head("Kolejność montażu")
    for i, t in enumerate(pr.steps, 1):
        para(f"{i}. {t}", 7.5)
    if pr.model.plates:
        head("Części szkieletu")
        para(", ".join(f"{pl.label} — {pl.name}" for pl in pr.model.plates), 7.5)
    if checks:
        head("Kontrola automatyczna projektu")
        for ch in checks:
            para(f"{'OK' if ch.ok else 'BŁĄD'} — {ch.name}: {ch.detail}", 7.5)
    return out
