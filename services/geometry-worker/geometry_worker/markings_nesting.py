"""Markings (okna/drzwi) oraz nesting paneli na wiele arkuszy."""

from __future__ import annotations

from .box_unfold import FacePanel, Marking, Point, UnfoldResult, marking_rect, panel_bbox
from .svg_export import SHEETS


def add_building_markings(result: UnfoldResult) -> UnfoldResult:
    for panel in result.panels:
        if panel.name == "front":
            # drzwi na środku ściany (pod szczytem: panel.y + roof portion ≈ R, ale mamy R w fold)
            # uproszczenie: drzwi i 2 okna w dolnej części panelu (ściana)
            wall_top = panel.y + max(panel.h * 0.35, 10)
            door_w, door_h = min(14.0, panel.w * 0.18), min(22.0, panel.h * 0.35)
            door_x = panel.x + panel.w / 2 - door_w / 2
            door_y = panel.y + panel.h - door_h - 4
            panel.markings.append(marking_rect(door_x, door_y, door_w, door_h, "door"))
            win_w, win_h = min(12.0, panel.w * 0.14), min(10.0, panel.h * 0.14)
            panel.markings.append(
                marking_rect(panel.x + 8, wall_top + 4, win_w, win_h, "window")
            )
            panel.markings.append(
                marking_rect(panel.x + panel.w - 8 - win_w, wall_top + 4, win_w, win_h, "window")
            )
        elif panel.name in {"left", "right"}:
            win_w, win_h = min(10.0, panel.w * 0.35), min(10.0, panel.h * 0.22)
            panel.markings.append(
                marking_rect(
                    panel.x + panel.w / 2 - win_w / 2,
                    panel.y + panel.h * 0.35,
                    win_w,
                    win_h,
                    "window",
                )
            )
        elif panel.name == "back":
            win_w, win_h = min(12.0, panel.w * 0.14), min(10.0, panel.h * 0.14)
            wall_top = panel.y + max(panel.h * 0.35, 10)
            panel.markings.append(
                marking_rect(panel.x + panel.w / 2 - win_w / 2, wall_top + 4, win_w, win_h, "window")
            )
    return result


def add_vehicle_markings(result: UnfoldResult) -> UnfoldResult:
    """Okna/drzwi dla bryły box użytej jako furgon/ciągnik."""
    for panel in result.panels:
        if panel.name == "front":
            # szyba + grill uproszczenie
            win_w = min(panel.w * 0.7, panel.w - 8)
            win_h = min(panel.h * 0.35, 18)
            panel.markings.append(
                marking_rect(
                    panel.x + (panel.w - win_w) / 2,
                    panel.y + 6,
                    win_w,
                    win_h,
                    "window",
                )
            )
        elif panel.name in {"left", "right"}:
            # drzwi + okno boczne
            door_w = min(16.0, panel.w * 0.28)
            door_h = min(panel.h * 0.7, panel.h - 6)
            panel.markings.append(
                marking_rect(panel.x + 4, panel.y + panel.h - door_h - 3, door_w, door_h, "door")
            )
            win_w = min(14.0, panel.w * 0.25)
            win_h = min(12.0, panel.h * 0.3)
            panel.markings.append(
                marking_rect(
                    panel.x + panel.w - win_w - 6,
                    panel.y + 8,
                    win_w,
                    win_h,
                    "window",
                )
            )
        elif panel.name == "back":
            # drzwi tylne / klapa
            door_w = min(panel.w * 0.8, panel.w - 8)
            door_h = min(panel.h * 0.75, panel.h - 6)
            panel.markings.append(
                marking_rect(
                    panel.x + (panel.w - door_w) / 2,
                    panel.y + panel.h - door_h - 3,
                    door_w,
                    door_h,
                    "door",
                )
            )
    return result


def add_wagon_markings(result: UnfoldResult) -> UnfoldResult:
    """Małe okienka / detale na burtach wagonu towarowego."""
    for panel in result.panels:
        if panel.name in {"left", "right", "front", "back"}:
            n = 3 if panel.w >= 40 else 2
            gap = panel.w / (n + 1)
            win_w = min(8.0, gap * 0.45)
            win_h = min(8.0, panel.h * 0.35)
            for i in range(n):
                cx = panel.x + gap * (i + 1) - win_w / 2
                cy = panel.y + panel.h * 0.3
                panel.markings.append(marking_rect(cx, cy, win_w, win_h, "window"))
    return result


def _shift_panel(panel: FacePanel, dx: float, dy: float) -> FacePanel:
    def sp(p: Point) -> Point:
        return Point(p.x + dx, p.y + dy)

    return FacePanel(
        id=panel.id,
        name=panel.name,
        label=panel.label,
        x=panel.x + dx,
        y=panel.y + dy,
        w=panel.w,
        h=panel.h,
        flaps=[[sp(p) for p in flap] for flap in panel.flaps],
        fold_lines=[(sp(a), sp(b)) for a, b in panel.fold_lines],
        cut_paths=[[sp(p) for p in path] for path in panel.cut_paths],
        markings=[
            Marking(kind=m.kind, points=[sp(p) for p in m.points]) for m in panel.markings
        ],
    )


def pack_panels_to_sheets(
    result: UnfoldResult,
    sheet: str = "A4",
    margin_mm: float = 8.0,
    gap_mm: float = 4.0,
    force_multisheet: bool = False,
    min_scale_single: float = 0.82,
) -> list[UnfoldResult]:
    """
    Jeśli cały net mieści się na 1 arkuszu ze skalą >= min_scale_single — 1 strona (skala w rendererze).
    W przeciwnym razie packing paneli 1:1 na wiele arkuszy.
    """
    sw, sh = SHEETS.get(sheet, SHEETS["A4"])
    usable_w = sw - 2 * margin_mm
    usable_h = sh - 2 * margin_mm - 20  # miejsce na tytuł/instrukcję

    fits_scale = min(usable_w / result.width_mm, usable_h / max(result.height_mm, 1))
    if not force_multisheet and fits_scale >= min_scale_single:
        return [result]

    # Packing półkowy
    items: list[tuple[FacePanel, float, float, float, float]] = []
    for panel in result.panels:
        minx, miny, maxx, maxy = panel_bbox(panel, pad=0.5)
        items.append((panel, minx, miny, maxx - minx, maxy - miny))

    items.sort(key=lambda t: t[3] * t[4], reverse=True)

    sheets: list[list[FacePanel]] = []
    cursor_x = margin_mm
    cursor_y = margin_mm + 14
    row_h = 0.0
    current: list[FacePanel] = []

    def flush() -> None:
        nonlocal current, cursor_x, cursor_y, row_h
        if current:
            sheets.append(current)
        current = []
        cursor_x = margin_mm
        cursor_y = margin_mm + 14
        row_h = 0.0

    for panel, minx, miny, bw, bh in items:
        if bw > usable_w or bh > usable_h:
            # panel większy niż arkusz — i tak wrzucamy (renderer przeskaluje stronę)
            if current:
                flush()
            dx = margin_mm - minx
            dy = (margin_mm + 14) - miny
            current.append(_shift_panel(panel, dx, dy))
            flush()
            continue

        if cursor_x + bw > margin_mm + usable_w:
            cursor_x = margin_mm
            cursor_y += row_h + gap_mm
            row_h = 0.0

        if cursor_y + bh > margin_mm + 14 + usable_h:
            flush()

        dx = cursor_x - minx
        dy = cursor_y - miny
        current.append(_shift_panel(panel, dx, dy))
        cursor_x += bw + gap_mm
        row_h = max(row_h, bh)

    if current:
        sheets.append(current)

    out: list[UnfoldResult] = []
    for i, panels in enumerate(sheets, start=1):
        max_x = max(panel_bbox(p)[2] for p in panels) + margin_mm
        max_y = max(panel_bbox(p)[3] for p in panels) + margin_mm
        page_instructions = [
            f"Arkusz {i}/{len(sheets)} — nesting paneli 1:1 (lub bliski).",
            *result.instructions,
        ]
        out.append(
            UnfoldResult(
                panels=panels,
                width_mm=max(max_x, sw),
                height_mm=max(max_y, sh * 0.5),
                instructions=page_instructions[:6],
            )
        )
    return out or [result]
