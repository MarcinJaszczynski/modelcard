"""Rozwijanie wagonu towarowego (skrzynia otwarta + podwozie + koła)."""

from __future__ import annotations

import math

from .box_unfold import FacePanel, Point, UnfoldResult, _rect, _trapezoid_flap


def unfold_wagon(
    length_mm: float,
    width_mm: float,
    height_mm: float,
    chassis_height_mm: float = 8.0,
    wheel_diameter_mm: float = 18.0,
    flap_mm: float = 8.0,
    wheel_segments: int = 20,
    margin_mm: float = 10.0,
) -> UnfoldResult:
    """
    Uproszczony wagon:
    - podłoga + 4 burty (otwarta skrzynia)
    - podwozie (prostokąt)
    - 2 koła (wielokąty ≈ koła) z zakładkami
    """
    L = length_mm  # długość (oś wzdłuż wagonu)
    W = width_mm   # szerokość
    H = height_mm
    CH = chassis_height_mm
    WD = wheel_diameter_mm
    F = flap_mm
    segs = max(12, min(wheel_segments, 36))
    R = WD / 2

    ox = margin_mm + F
    oy = margin_mm + F

    panels: list[FacePanel] = []

    # Layout:
    #        [FRONT]
    # [LEFT] [FLOOR] [RIGHT]
    #        [BACK]
    #        [CHASSIS]
    #   [WHEEL1] [WHEEL2]

    floor_x, floor_y = ox + H, oy + H
    front_x, front_y = floor_x, oy
    back_x, back_y = floor_x, floor_y + W
    left_x, left_y = ox, floor_y
    right_x, right_y = floor_x + L, floor_y
    chassis_x, chassis_y = floor_x, back_y + H + 6

    def wall(pid: str, name: str, label: str, x: float, y: float, pw: float, ph: float, flaps: list[str]) -> FacePanel:
        panel = FacePanel(
            id=pid,
            name=name,
            label=label,
            x=x,
            y=y,
            w=pw,
            h=ph,
            cut_paths=[_rect(x, y, pw, ph)],
            fold_lines=[
                (Point(x, y), Point(x + pw, y)),
                (Point(x + pw, y), Point(x + pw, y + ph)),
                (Point(x + pw, y + ph), Point(x, y + ph)),
                (Point(x, y + ph), Point(x, y)),
            ],
        )
        for side in flaps:
            if side == "top":
                flap = _trapezoid_flap(x, y, pw, F, "top")
                fold = (Point(x, y), Point(x + pw, y))
            elif side == "bottom":
                flap = _trapezoid_flap(x, y + ph, pw, F, "bottom")
                fold = (Point(x, y + ph), Point(x + pw, y + ph))
            elif side == "left":
                flap = _trapezoid_flap(x, y, ph, F, "left")
                fold = (Point(x, y), Point(x, y + ph))
            else:
                flap = _trapezoid_flap(x + pw, y, ph, F, "right")
                fold = (Point(x + pw, y), Point(x + pw, y + ph))
            panel.flaps.append(flap)
            panel.cut_paths.append(flap)
            panel.fold_lines.append(fold)
        panels.append(panel)
        return panel

    # 1 FLOOR — bez zakładek zewnętrznych (łączy się z burtami w netcie)
    wall("1", "floor", "1 PODŁOGA", floor_x, floor_y, L, W, [])

    # 2 FRONT burta (L × H) — zakładka górna
    wall("2", "front", "2 PRZÓD", front_x, front_y, L, H, ["top"])

    # 3 BACK
    wall("3", "back", "3 TYŁ", back_x, back_y, L, H, ["bottom"])

    # 4 LEFT
    wall("4", "left", "4 LEWY", left_x, left_y, H, W, ["left", "top", "bottom"])

    # 5 RIGHT
    wall("5", "right", "5 PRAWY", right_x, right_y, H, W, ["right", "top", "bottom"])

    # 6 CHASSIS
    wall("6", "chassis", "6 PODWOZIE", chassis_x, chassis_y, L, CH, ["top", "bottom", "left", "right"])

    def wheel(pid: str, name: str, label: str, cx: float, cy: float) -> FacePanel:
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
            w=WD,
            h=WD,
            cut_paths=[pts],
            fold_lines=[],
        )
        for i in range(segs):
            a = pts[i]
            b = pts[(i + 1) % segs]
            ex, ey = b.x - a.x, b.y - a.y
            length = math.hypot(ex, ey) or 1.0
            nx, ny = ey / length, -ex / length
            midx, midy = (a.x + b.x) / 2, (a.y + b.y) / 2
            if (midx - cx) * nx + (midy - cy) * ny < 0:
                nx, ny = -nx, -ny
            taper = min(1.5, length / 4, F / 2)
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
        panels.append(panel)
        return panel

    wheel_y = chassis_y + CH + F + R + 8
    wheel("7", "wheel_a", "7 KOŁO", floor_x + R + 4, wheel_y)
    wheel("8", "wheel_b", "8 KOŁO", floor_x + L - R - 4, wheel_y)

    total_w = right_x + H + F + margin_mm
    total_h = wheel_y + R + F + margin_mm

    instructions = [
        "Wytnij po liniach ciągłych, zegnij po przerywanych.",
        "Zegnij burty (2–5) w górę od podłogi (1) i sklej narożniki zakładkami.",
        "Doklej podwozie (6) od spodu podłogi.",
        "Zwiń zakładki kół (7, 8) i przyklej koła do boków podwozia.",
        f"Skrzynia {L:.1f}×{W:.1f}×{H:.1f} mm, podwozie {CH:.1f} mm, koła Ø{WD:.1f} mm.",
    ]

    return UnfoldResult(
        panels=panels,
        width_mm=total_w,
        height_mm=total_h,
        instructions=instructions,
    )
