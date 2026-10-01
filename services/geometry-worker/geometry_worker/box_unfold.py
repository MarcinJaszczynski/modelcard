"""Rozwijanie prostopadłościanu z zakładkami sklejki."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Point:
    x: float
    y: float


@dataclass
class Marking:
    kind: str  # window | door | detail
    points: list[Point]


@dataclass
class FacePanel:
    id: str
    name: str
    label: str
    # prostokąt panelu: origin + size (bez zakładek)
    x: float
    y: float
    w: float
    h: float
    # zakładki: lista poligonów (cięcie zewnętrzne)
    flaps: list[list[Point]] = field(default_factory=list)
    # linie gięcia (wewnętrzne krawędzie)
    fold_lines: list[tuple[Point, Point]] = field(default_factory=list)
    # linie cięcia (obrys + zakładki)
    cut_paths: list[list[Point]] = field(default_factory=list)
    # markings graficzne (okna, drzwi) — tylko druk, nie cięcie
    markings: list[Marking] = field(default_factory=list)


@dataclass
class UnfoldResult:
    panels: list[FacePanel]
    width_mm: float
    height_mm: float
    instructions: list[str]


def panel_bbox(panel: FacePanel, pad: float = 0.0) -> tuple[float, float, float, float]:
    """(min_x, min_y, max_x, max_y) po wszystkich cut_paths."""
    xs: list[float] = []
    ys: list[float] = []
    for path in panel.cut_paths:
        for p in path:
            xs.append(p.x)
            ys.append(p.y)
    if not xs:
        return panel.x, panel.y, panel.x + panel.w, panel.y + panel.h
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def marking_rect(x: float, y: float, w: float, h: float, kind: str = "window") -> Marking:
    return Marking(kind=kind, points=_rect(x, y, w, h))


def _rect(x: float, y: float, w: float, h: float) -> list[Point]:
    return [
        Point(x, y),
        Point(x + w, y),
        Point(x + w, y + h),
        Point(x, y + h),
    ]


def _trapezoid_flap(
    x: float,
    y: float,
    length: float,
    depth: float,
    side: str,
    taper: float = 2.0,
) -> list[Point]:
    """Zakładka trapezowa przy krawędzi prostokąta."""
    t = min(taper, length / 4, depth / 2)
    if side == "top":
        return [
            Point(x, y),
            Point(x + length, y),
            Point(x + length - t, y - depth),
            Point(x + t, y - depth),
        ]
    if side == "bottom":
        return [
            Point(x, y),
            Point(x + length, y),
            Point(x + length - t, y + depth),
            Point(x + t, y + depth),
        ]
    if side == "left":
        return [
            Point(x, y),
            Point(x, y + length),
            Point(x - depth, y + length - t),
            Point(x - depth, y + t),
        ]
    if side == "right":
        return [
            Point(x, y),
            Point(x, y + length),
            Point(x + depth, y + length - t),
            Point(x + depth, y + t),
        ]
    raise ValueError(f"Unknown flap side: {side}")


def unfold_box(
    width_mm: float,
    height_mm: float,
    depth_mm: float,
    flap_mm: float = 8.0,
    margin_mm: float = 10.0,
) -> UnfoldResult:
    """
    Klasyczny krzyż kartonowy (net):

              [TOP]
        [L] [FRONT] [R] [BACK]
              [BOTTOM]

    Zakładki na zewnętrznych krawędziach do sklejania.
    Jednostki: mm.
    """
    W, H, D, F = width_mm, height_mm, depth_mm, flap_mm

    # Layout origin (po marginesie i miejscu na górne zakładki)
    ox = margin_mm + F
    oy = margin_mm + F

    # Pozycje paneli
    front = (ox + D, oy + D)
    left = (ox, oy + D)
    right = (ox + D + W, oy + D)
    back = (ox + D + W + D, oy + D)
    top = (ox + D, oy)
    bottom = (ox + D, oy + D + H)

    panels: list[FacePanel] = []

    def make_panel(
        pid: str,
        name: str,
        label: str,
        origin: tuple[float, float],
        pw: float,
        ph: float,
        flaps_spec: list[tuple[str, float]],
    ) -> FacePanel:
        x, y = origin
        panel = FacePanel(
            id=pid,
            name=name,
            label=label,
            x=x,
            y=y,
            w=pw,
            h=ph,
            cut_paths=[_rect(x, y, pw, ph)],
        )

        # fold lines = krawędzie panelu (wewnątrz netu)
        panel.fold_lines = [
            (Point(x, y), Point(x + pw, y)),
            (Point(x + pw, y), Point(x + pw, y + ph)),
            (Point(x + pw, y + ph), Point(x, y + ph)),
            (Point(x, y + ph), Point(x, y)),
        ]

        for side, length in flaps_spec:
            if side == "top":
                flap = _trapezoid_flap(x, y, length, F, "top")
                fold = (Point(x, y), Point(x + length, y))
            elif side == "bottom":
                flap = _trapezoid_flap(x, y + ph, length, F, "bottom")
                fold = (Point(x, y + ph), Point(x + length, y + ph))
            elif side == "left":
                flap = _trapezoid_flap(x, y, length, F, "left")
                fold = (Point(x, y), Point(x, y + length))
            else:
                flap = _trapezoid_flap(x + pw, y, length, F, "right")
                fold = (Point(x + pw, y), Point(x + pw, y + length))

            panel.flaps.append(flap)
            panel.cut_paths.append(flap)
            panel.fold_lines.append(fold)

        panels.append(panel)
        return panel

    # 1 FRONT — zakładki góra/dół już przez top/bottom; boczne łączą z L/R w netcie
    make_panel("1", "front", "1 PRZÓD", front, W, H, [("top", W), ("bottom", W)])

    # 2 LEFT
    make_panel("2", "left", "2 LEWY", left, D, H, [("left", H), ("top", D), ("bottom", D)])

    # 3 RIGHT
    make_panel("3", "right", "3 PRAWY", right, D, H, [("top", D), ("bottom", D)])

    # 4 BACK — zakładka prawa do sklejenia z lewym
    make_panel("4", "back", "4 TYŁ", back, W, H, [("right", H), ("top", W), ("bottom", W)])

    # 5 TOP — bez dolnej (łączy z front), zakładki pozostałe
    make_panel("5", "top", "5 GÓRA", top, W, D, [("top", W), ("left", D), ("right", D)])

    # 6 BOTTOM
    make_panel("6", "bottom", "6 DÓŁ", bottom, W, D, [("bottom", W), ("left", D), ("right", D)])

    total_w = ox + D + W + D + W + F + margin_mm
    total_h = oy + D + H + D + F + margin_mm

    instructions = [
        "Wytnij po liniach ciągłych (cięcie).",
        "Zegnij po liniach przerywanych (gięcie).",
        "Sklej zakładki od wewnątrz, zaczynając od ścian bocznych (2, 3) do przodu (1).",
        "Doklej tył (4) zakładką do lewego boku (2).",
        "Zamknij górę (5) i dół (6).",
        f"Wymiary bryły: {W:.1f} × {H:.1f} × {D:.1f} mm, zakładka {F:.1f} mm.",
    ]

    return UnfoldResult(
        panels=panels,
        width_mm=total_w,
        height_mm=total_h,
        instructions=instructions,
    )
