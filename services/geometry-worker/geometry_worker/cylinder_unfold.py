"""Rozwijanie walca / tuby kartonowej z denkami i zakładką."""

from __future__ import annotations

import math

from .box_unfold import FacePanel, Point, UnfoldResult, _rect, _trapezoid_flap


def unfold_cylinder(
    diameter_mm: float,
    height_mm: float,
    flap_mm: float = 8.0,
    segments: int = 24,
    margin_mm: float = 10.0,
) -> UnfoldResult:
    """
    Net tuby:
    - ściana boczna: prostokąt (π·d × h) + zakładka pionowa
    - denko górne/dolne: wielokąt foremny ≈ koło z zakładkami na krawędziach
    """
    D = diameter_mm
    H = height_mm
    F = flap_mm
    R = D / 2
    circ = math.pi * D
    segs = max(12, min(segments, 48))

    ox = margin_mm + F
    oy = margin_mm + F

    panels: list[FacePanel] = []

    # 1 — ściana boczna
    side_x, side_y = ox, oy + D + F + 4
    side = FacePanel(
        id="1",
        name="side",
        label="1 BOK",
        x=side_x,
        y=side_y,
        w=circ,
        h=H,
        cut_paths=[_rect(side_x, side_y, circ, H)],
        fold_lines=[
            (Point(side_x, side_y), Point(side_x + circ, side_y)),
            (Point(side_x, side_y + H), Point(side_x + circ, side_y + H)),
            (Point(side_x, side_y), Point(side_x, side_y + H)),
            (Point(side_x + circ, side_y), Point(side_x + circ, side_y + H)),
        ],
    )
    # zakładka sklejenia pionowa
    glue = _trapezoid_flap(side_x + circ, side_y, H, F, "right")
    side.flaps.append(glue)
    side.cut_paths.append(glue)
    side.fold_lines.append(
        (Point(side_x + circ, side_y), Point(side_x + circ, side_y + H))
    )
    panels.append(side)

    def make_cap(pid: str, name: str, label: str, cx: float, cy: float) -> FacePanel:
        # wielokąt foremny
        pts: list[Point] = []
        for i in range(segs):
            ang = -math.pi / 2 + (2 * math.pi * i / segs)
            pts.append(Point(cx + R * math.cos(ang), cy + R * math.sin(ang)))

        panel = FacePanel(
            id=pid,
            name=name,
            label=label,
            x=cx - R,
            y=cy - R,
            w=D,
            h=D,
            cut_paths=[pts],
            fold_lines=[],
        )

        # zakładki na każdym boku wielokąta
        for i in range(segs):
            a = pts[i]
            b = pts[(i + 1) % segs]
            # wektor krawędzi i normalna na zewnątrz
            ex, ey = b.x - a.x, b.y - a.y
            length = math.hypot(ex, ey) or 1.0
            nx, ny = ey / length, -ex / length
            # upewnij się, że normalna idzie od środka na zewnątrz
            midx, midy = (a.x + b.x) / 2, (a.y + b.y) / 2
            if (midx - cx) * nx + (midy - cy) * ny < 0:
                nx, ny = -nx, -ny

            taper = min(2.0, length / 4, F / 2)
            # trapez wzdłuż krawędzi
            ux, uy = ex / length, ey / length
            flap = [
                a,
                b,
                Point(b.x - ux * taper + nx * F, b.y - uy * taper + ny * F),
                Point(a.x + ux * taper + nx * F, a.y + uy * taper + ny * F),
            ]
            panel.flaps.append(flap)
            panel.cut_paths.append(flap)
            panel.fold_lines.append((a, b))

        return panel

    top = make_cap("2", "top", "2 GÓRA", ox + R, oy + R)
    bottom = make_cap(
        "3",
        "bottom",
        "3 DÓŁ",
        ox + D + F + 8 + R,
        oy + R,
    )
    panels.extend([top, bottom])

    total_w = max(side_x + circ + F, ox + D + F + 8 + D) + margin_mm
    total_h = side_y + H + margin_mm

    instructions = [
        "Wytnij po liniach ciągłych.",
        "Zegnij zakładki denek (linie przerywane na obwodzie).",
        "Zwiń bok (1) w tubę i sklej pionową zakładką od wewnątrz.",
        "Doklej denko górne (2) i dolne (3) zakładkami do środka tuby.",
        f"Średnica {D:.1f} mm, wysokość {H:.1f} mm, zakładka {F:.1f} mm, segmenty denka {segs}.",
    ]

    return UnfoldResult(
        panels=panels,
        width_mm=total_w,
        height_mm=total_h,
        instructions=instructions,
    )
