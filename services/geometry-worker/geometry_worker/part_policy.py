"""Reguły minimalnych części — podklejanie zamiast mikro-sklejania."""

from __future__ import annotations

from dataclasses import dataclass

from .box_unfold import FacePanel, UnfoldResult


@dataclass
class PartPolicy:
    min_part_mm: float = 6.0
    min_flap_mm: float = 4.0
    laminate_thickness_mm: float = 1.0


def analyze_parts(result: UnfoldResult, policy: PartPolicy | None = None) -> dict:
    policy = policy or PartPolicy()
    too_small: list[dict] = []
    ok: list[dict] = []

    for panel in result.panels:
        shortest = min(panel.w, panel.h)
        entry = {
            "id": panel.id,
            "name": panel.name,
            "label": panel.label,
            "w_mm": round(panel.w, 2),
            "h_mm": round(panel.h, 2),
            "shortest_mm": round(shortest, 2),
        }
        if shortest < policy.min_part_mm:
            entry["action"] = "laminate_then_cut"
            entry["note"] = (
                f"Część < {policy.min_part_mm} mm — podklej na tekturę "
                f"{policy.laminate_thickness_mm} mm i wytnij, nie sklejaj mikro-elementów."
            )
            too_small.append(entry)
        else:
            entry["action"] = "cut_print"
            ok.append(entry)

    return {
        "min_part_mm": policy.min_part_mm,
        "laminate_thickness_mm": policy.laminate_thickness_mm,
        "ok_count": len(ok),
        "laminate_count": len(too_small),
        "parts_ok": ok,
        "parts_laminate": too_small,
        "instruction_extra": (
            [
                f"UWAGA: {len(too_small)} części poniżej {policy.min_part_mm} mm — "
                f"podklej na tekturę {policy.laminate_thickness_mm} mm i wytnij."
            ]
            if too_small
            else []
        ),
    }


def apply_policy_notes(result: UnfoldResult, analysis: dict) -> UnfoldResult:
    extras = analysis.get("instruction_extra") or []
    if extras:
        result.instructions = [*extras, *result.instructions]
    for item in analysis.get("parts_laminate") or []:
        for panel in result.panels:
            if panel.id == item["id"]:
                panel.label = f"{panel.label} ★podklej"
    return result
