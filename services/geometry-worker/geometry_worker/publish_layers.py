"""
Warstwy produktów w stylu wydawniczym:
- parts: rozwinięcia z teksturą/markings
- instructions: schemat montażu (osobny arkusz)
- formers: wręgi / szkielet do tektury grubszej
"""

from __future__ import annotations

from .box_unfold import FacePanel, Point, UnfoldResult, _rect


def build_instruction_page(
    result: UnfoldResult,
    title: str,
    sheet_w: float = 210.0,
    sheet_h: float = 297.0,
) -> str:
    """Prosty arkusz instrukcji SVG (nie jest kopią cudzych plansz)."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{sheet_w}mm" height="{sheet_h}mm" '
        f'viewBox="0 0 {sheet_w} {sheet_h}">',
        f"<title>Instrukcja — {_esc(title)}</title>",
        "<style><![CDATA[",
        "  .t{font-family:Helvetica,Arial,sans-serif;fill:#111}",
        "  .h{font-size:5px;font-weight:bold}",
        "  .b{font-size:3.2px}",
        "  .box{fill:#f7f3ea;stroke:#111;stroke-width:0.35}",
        "  .arrow{stroke:#333;stroke-width:0.4;fill:none;marker-end:url(#arrow)}",
        "]]></style>",
        "<defs>",
        '  <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">',
        '    <path d="M0,0 L6,3 L0,6 Z" fill="#333"/>',
        "  </marker>",
        "</defs>",
        f'<rect x="0" y="0" width="{sheet_w}" height="{sheet_h}" fill="#fff"/>',
        f'<text class="t h" x="10" y="14">INSTRUKCJA MONTAŻU</text>',
        f'<text class="t b" x="10" y="20">{_esc(title)}</text>',
        '<text class="t b" x="10" y="26">Konwencja: linie ciągłe = cięcie · przerywane = gięcie · zakładki sklejać od wewnątrz.</text>',
    ]

    # Miniatury paneli w siatce
    cols = 3
    cell_w, cell_h = 60.0, 42.0
    ox, oy = 12.0, 34.0
    for i, panel in enumerate(result.panels):
        col, row = i % cols, i // cols
        x = ox + col * (cell_w + 6)
        y = oy + row * (cell_h + 8)
        if y + cell_h > sheet_h - 70:
            break
        lines.append(f'<rect class="box" x="{x}" y="{y}" width="{cell_w}" height="{cell_h}"/>')
        lines.append(
            f'<text class="t b" x="{x + cell_w/2}" y="{y + cell_h/2}" text-anchor="middle">'
            f'{_esc(panel.label)}</text>'
        )
        if i > 0:
            # strzałka od poprzedniego
            px = ox + ((i - 1) % cols) * (cell_w + 6) + cell_w
            py = oy + ((i - 1) // cols) * (cell_h + 8) + cell_h / 2
            if (i - 1) // cols == row:
                lines.append(
                    f'<line class="arrow" x1="{px + 1}" y1="{py}" x2="{x - 1}" y2="{y + cell_h/2}"/>'
                )

    # Kroki tekstowe
    y0 = sheet_h - 8 - max(len(result.instructions), 1) * 4.2
    lines.append(f'<text class="t h" x="10" y="{y0}">Kroki sklejania</text>')
    for idx, step in enumerate(result.instructions, start=1):
        lines.append(
            f'<text class="t b" x="10" y="{y0 + idx * 4.2}">{idx}. {_esc(step)}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def build_formers_for_box(
    width_mm: float,
    height_mm: float,
    depth_mm: float,
    thickness_mm: float = 1.0,
    margin_mm: float = 10.0,
) -> UnfoldResult:
    """
    Formierze (wręgi) — uproszczony szkielet jak laserowy szkielet w ekosystemie wycinanek:
    2 wręgi poprzeczne + 2 podłużne + dno wzmacniające.
    """
    W, H, D = width_mm, height_mm, depth_mm
    # kompensacja grubości sklejek zewnętrznych (uproszczenie)
    inner_w = max(W - 2 * thickness_mm, W * 0.9)
    inner_d = max(D - 2 * thickness_mm, D * 0.9)
    inner_h = max(H - thickness_mm, H * 0.9)

    panels: list[FacePanel] = []
    x = margin_mm
    y = margin_mm

    def add(pid: str, name: str, label: str, pw: float, ph: float) -> None:
        nonlocal x, y
        if x + pw > 190:
            x = margin_mm
            y += 55
        panels.append(
            FacePanel(
                id=pid,
                name=name,
                label=label,
                x=x,
                y=y,
                w=pw,
                h=ph,
                cut_paths=[_rect(x, y, pw, ph)],
                fold_lines=[],
            )
        )
        x += pw + 8

    add("F1", "former_bulkhead_a", "F1 WRĘGA", inner_w, inner_h)
    add("F2", "former_bulkhead_b", "F2 WRĘGA", inner_w, inner_h)
    add("F3", "former_longeron_l", "F3 WZDŁUŻNICA", inner_d, inner_h * 0.6)
    add("F4", "former_longeron_r", "F4 WZDŁUŻNICA", inner_d, inner_h * 0.6)
    add("F5", "former_floor", "F5 DNO", inner_w, inner_d)

    return UnfoldResult(
        panels=panels,
        width_mm=210,
        height_mm=max(y + 60, 120),
        instructions=[
            f"Formierze wycinać z tektury ~{thickness_mm:g} mm (nie z arkusza druku 0,2 mm).",
            "Wręgi F1/F2 wstawić poprzecznie w kadłub/skrzynię.",
            "Wzdłużnice F3/F4 i dno F5 wzmacniają konstrukcję przed oklejeniem.",
            "Po sklejeniu szkieletu nakładać zewnętrzne rozwinięcia z arkuszy części.",
        ],
    )


def build_formers_for_building(
    width_mm: float,
    depth_mm: float,
    wall_height_mm: float,
    roof_rise_mm: float,
    thickness_mm: float = 1.0,
    margin_mm: float = 10.0,
) -> UnfoldResult:
    W, D, H, R = width_mm, depth_mm, wall_height_mm, roof_rise_mm
    panels: list[FacePanel] = []
    x = margin_mm
    y = margin_mm

    def add(pid: str, name: str, label: str, pts: list[Point]) -> None:
        nonlocal x, y
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        pw, ph = max(xs) - min(xs), max(ys) - min(ys)
        # przesuń lokalnie
        dx, dy = x - min(xs), y - min(ys)
        shifted = [Point(p.x + dx, p.y + dy) for p in pts]
        if x + pw > 190:
            x = margin_mm
            y += 70
            dx, dy = x - min(xs), y - min(ys)
            shifted = [Point(p.x + dx, p.y + dy) for p in pts]
        panels.append(
            FacePanel(
                id=pid,
                name=name,
                label=label,
                x=x,
                y=y,
                w=pw,
                h=ph,
                cut_paths=[shifted],
            )
        )
        x += pw + 8

    # szczyt (pięciokąt) ×2
    gable = [
        Point(0, 0),
        Point(W / 2, -R),
        Point(W, 0),
        Point(W, H),
        Point(0, H),
    ]
    add("F1", "gable_a", "F1 SZCZYT", gable)
    add("F2", "gable_b", "F2 SZCZYT", gable)
    add("F3", "floor", "F3 PODŁOGA", _rect(0, 0, W, D))
    add("F4", "wall_brace", "F4 WZMOCNIENIE", _rect(0, 0, D, H))

    return UnfoldResult(
        panels=panels,
        width_mm=210,
        height_mm=max(y + 80, 140),
        instructions=[
            f"Szczyty i wzmocnienia z tektury ~{thickness_mm:g} mm.",
            "Najpierw skleić szkielet (F1–F4), potem okleić częściami z arkuszy druku.",
        ],
    )


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
