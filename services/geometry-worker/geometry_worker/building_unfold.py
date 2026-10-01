"""Rozwijanie budynku z dachem dwuspadowym."""

from __future__ import annotations

import math

from .box_unfold import FacePanel, Point, UnfoldResult, _rect, _trapezoid_flap


def unfold_building(
    width_mm: float,
    depth_mm: float,
    wall_height_mm: float,
    roof_rise_mm: float,
    flap_mm: float = 8.0,
    margin_mm: float = 10.0,
) -> UnfoldResult:
    """
    Net prostego domu:
    - front/back: ściana + szczyt (pięciokąt)
    - left/right: prostokątne ściany
    - 2 połacie dachu (prostokąty o szerokości = długość skosu)
    """
    W = width_mm
    D = depth_mm
    H = wall_height_mm
    R = roof_rise_mm
    F = flap_mm
    slant = math.hypot(D / 2.0, R)  # długość skosu połaci

    ox = margin_mm + F
    oy = margin_mm + F

    panels: list[FacePanel] = []

    def gable_points(x: float, y: float) -> list[Point]:
        # y = top of bounding box (peak at y)
        # peak, right eave, right bottom, left bottom, left eave
        return [
            Point(x + W / 2, y),
            Point(x + W, y + R),
            Point(x + W, y + R + H),
            Point(x, y + R + H),
            Point(x, y + R),
        ]

    # Layout:
    #          [ROOF L] [ROOF R]
    #   [LEFT] [FRONT]  [RIGHT] [BACK]
    front_h = H + R
    front_x = ox + D
    front_y = oy + slant + 6

    left_x, left_y = ox, front_y + R  # align with wall part of front
    right_x = front_x + W
    right_y = front_y + R
    back_x = right_x + D
    back_y = front_y

    roof_l_x, roof_l_y = front_x, oy
    roof_r_x = front_x + W + 4
    roof_r_y = oy

    # 1 FRONT (gable)
    front_pts = gable_points(front_x, front_y)
    front = FacePanel(
        id="1",
        name="front",
        label="1 PRZÓD",
        x=front_x,
        y=front_y,
        w=W,
        h=front_h,
        cut_paths=[front_pts],
        fold_lines=[
            # linia okapu (gięcie dachu względem ściany — informacyjna)
            (Point(front_x, front_y + R), Point(front_x + W, front_y + R)),
            (Point(front_x, front_y + R), Point(front_x, front_y + R + H)),
            (Point(front_x + W, front_y + R), Point(front_x + W, front_y + R + H)),
            (Point(front_x, front_y + R + H), Point(front_x + W, front_y + R + H)),
        ],
    )
    # zakładki dolna + boków na ścianie
    bottom = _trapezoid_flap(front_x, front_y + R + H, W, F, "bottom")
    front.flaps.append(bottom)
    front.cut_paths.append(bottom)
    front.fold_lines.append(
        (Point(front_x, front_y + R + H), Point(front_x + W, front_y + R + H))
    )
    panels.append(front)

    # 2 LEFT
    left = FacePanel(
        id="2",
        name="left",
        label="2 LEWY",
        x=left_x,
        y=left_y,
        w=D,
        h=H,
        cut_paths=[_rect(left_x, left_y, D, H)],
        fold_lines=[
            (Point(left_x, left_y), Point(left_x + D, left_y)),
            (Point(left_x, left_y + H), Point(left_x + D, left_y + H)),
            (Point(left_x, left_y), Point(left_x, left_y + H)),
            (Point(left_x + D, left_y), Point(left_x + D, left_y + H)),
        ],
    )
    for side, length, origin in [
        ("left", H, (left_x, left_y)),
        ("top", D, (left_x, left_y)),
        ("bottom", D, (left_x, left_y + H)),
    ]:
        if side == "left":
            flap = _trapezoid_flap(left_x, left_y, length, F, "left")
            fold = (Point(left_x, left_y), Point(left_x, left_y + H))
        elif side == "top":
            flap = _trapezoid_flap(left_x, left_y, length, F, "top")
            fold = (Point(left_x, left_y), Point(left_x + D, left_y))
        else:
            flap = _trapezoid_flap(left_x, left_y + H, length, F, "bottom")
            fold = (Point(left_x, left_y + H), Point(left_x + D, left_y + H))
        left.flaps.append(flap)
        left.cut_paths.append(flap)
        left.fold_lines.append(fold)
    panels.append(left)

    # 3 RIGHT
    right = FacePanel(
        id="3",
        name="right",
        label="3 PRAWY",
        x=right_x,
        y=right_y,
        w=D,
        h=H,
        cut_paths=[_rect(right_x, right_y, D, H)],
        fold_lines=[
            (Point(right_x, right_y), Point(right_x + D, right_y)),
            (Point(right_x, right_y + H), Point(right_x + D, right_y + H)),
            (Point(right_x, right_y), Point(right_x, right_y + H)),
            (Point(right_x + D, right_y), Point(right_x + D, right_y + H)),
        ],
    )
    for side in ("top", "bottom", "right"):
        if side == "top":
            flap = _trapezoid_flap(right_x, right_y, D, F, "top")
            fold = (Point(right_x, right_y), Point(right_x + D, right_y))
        elif side == "bottom":
            flap = _trapezoid_flap(right_x, right_y + H, D, F, "bottom")
            fold = (Point(right_x, right_y + H), Point(right_x + D, right_y + H))
        else:
            flap = _trapezoid_flap(right_x + D, right_y, H, F, "right")
            fold = (Point(right_x + D, right_y), Point(right_x + D, right_y + H))
        right.flaps.append(flap)
        right.cut_paths.append(flap)
        right.fold_lines.append(fold)
    panels.append(right)

    # 4 BACK (gable)
    back_pts = gable_points(back_x, back_y)
    back = FacePanel(
        id="4",
        name="back",
        label="4 TYŁ",
        x=back_x,
        y=back_y,
        w=W,
        h=front_h,
        cut_paths=[back_pts],
        fold_lines=[
            (Point(back_x, back_y + R), Point(back_x + W, back_y + R)),
            (Point(back_x, back_y + R), Point(back_x, back_y + R + H)),
            (Point(back_x + W, back_y + R), Point(back_x + W, back_y + R + H)),
            (Point(back_x, back_y + R + H), Point(back_x + W, back_y + R + H)),
        ],
    )
    bflap = _trapezoid_flap(back_x, back_y + R + H, W, F, "bottom")
    back.flaps.append(bflap)
    back.cut_paths.append(bflap)
    panels.append(back)

    # 5 / 6 ROOF halves — W × slant
    def roof_panel(pid: str, name: str, label: str, x: float, y: float) -> FacePanel:
        panel = FacePanel(
            id=pid,
            name=name,
            label=label,
            x=x,
            y=y,
            w=W,
            h=slant,
            cut_paths=[_rect(x, y, W, slant)],
            fold_lines=[
                (Point(x, y), Point(x + W, y)),
                (Point(x, y + slant), Point(x + W, y + slant)),
                (Point(x, y), Point(x, y + slant)),
                (Point(x + W, y), Point(x + W, y + slant)),
            ],
        )
        # zakładki na trzech krawędziach (kalenica bez lub z małą)
        for side in ("top", "left", "right"):
            if side == "top":
                flap = _trapezoid_flap(x, y, W, F, "top")
                fold = (Point(x, y), Point(x + W, y))
            elif side == "left":
                flap = _trapezoid_flap(x, y, slant, F, "left")
                fold = (Point(x, y), Point(x, y + slant))
            else:
                flap = _trapezoid_flap(x + W, y, slant, F, "right")
                fold = (Point(x + W, y), Point(x + W, y + slant))
            panel.flaps.append(flap)
            panel.cut_paths.append(flap)
            panel.fold_lines.append(fold)
        return panel

    panels.append(roof_panel("5", "roof_left", "5 DACH L", roof_l_x, roof_l_y))
    panels.append(roof_panel("6", "roof_right", "6 DACH P", roof_r_x, roof_r_y))

    total_w = back_x + W + F + margin_mm
    total_h = front_y + front_h + F + margin_mm

    instructions = [
        "Wytnij po liniach ciągłych, zegnij po przerywanych.",
        "Sklej ściany boczne (2, 3) do przodu (1), potem tył (4).",
        "Zegnij szczyty (trójkąty na 1 i 4) — to podpora dachu.",
        "Doklej połacie dachu (5, 6) zakładkami do szczytów i kalenicy.",
        f"Bryła: {W:.1f}×{D:.1f} mm, ściana {H:.1f} mm, wznios dachu {R:.1f} mm, skos {slant:.1f} mm.",
    ]

    return UnfoldResult(
        panels=panels,
        width_mm=total_w,
        height_mm=total_h,
        instructions=instructions,
    )
