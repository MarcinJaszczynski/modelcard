"""CLI i orkiestracja generacji / analizy skanów."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .box_unfold import unfold_box
from .building_unfold import unfold_building
from .cylinder_unfold import unfold_cylinder
from .fighter_unfold import unfold_fighter
from .markings_nesting import (
    add_building_markings,
    add_vehicle_markings,
    add_wagon_markings,
    pack_panels_to_sheets,
)
from .part_policy import PartPolicy, analyze_parts, apply_policy_notes
from .pdf_export import write_pdf_pages
from .publish_layers import (
    build_formers_for_box,
    build_formers_for_building,
    build_instruction_page,
)
from .scan_analyze import analyze_scan
from .style_recipe import resolve_recipe
from .styles import PRESETS, resolve_style
from .svg_export import SHEETS, write_svg_pages
from .texture_bake import bake_scheme_textures, list_schemes
from .wagon_unfold import unfold_wagon


def generate_from_payload(payload: dict) -> dict:
    shape = payload.get("shape", "box")
    params = payload.get("parameters") or {}
    output_dir = Path(payload["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    sheet = str(params.get("sheet", "A4"))
    flap = float(params.get("flap_mm", 8))
    style_key = str(params.get("style", "clean"))
    style = resolve_style(style_key)
    recipe = resolve_recipe(params)
    markings = bool(params.get("markings", True))
    force_multi = bool(params.get("multisheet", False))
    with_instructions = bool(params.get("instructions", True))
    with_formers = bool(params.get("formers", False))
    former_thickness = float(params.get("former_thickness_mm", 1.0))
    series = str(params.get("series", "beginner"))
    scale = str(params.get("scale", "1:25"))
    profile = recipe.profile

    if sheet not in SHEETS:
        return {"ok": False, "error": f"Unsupported sheet: {sheet}"}
    if style_key.lower() not in PRESETS:
        return {
            "ok": False,
            "error": f"Unsupported style: {style_key}. Available: {', '.join(PRESETS)}",
        }

    if shape == "box":
        width = float(params.get("width_mm", 80))
        height = float(params.get("height_mm", 50))
        depth = float(params.get("depth_mm", 40))
        result = unfold_box(width, height, depth, flap_mm=flap)
        if markings and params.get("markings_profile") == "vehicle":
            result = add_vehicle_markings(result)
        title = f"Prostopadłościan {width:g}×{height:g}×{depth:g} mm"
    elif shape == "cylinder":
        diameter = float(params.get("diameter_mm", params.get("width_mm", 50)))
        height = float(params.get("height_mm", 80))
        segments = int(params.get("segments", 24))
        result = unfold_cylinder(
            diameter, height, flap_mm=flap, segments=segments
        )
        title = f"Walec Ø{diameter:g}×{height:g} mm"
    elif shape == "building":
        width = float(params.get("width_mm", 80))
        depth = float(params.get("depth_mm", 60))
        wall_h = float(params.get("wall_height_mm", params.get("height_mm", 45)))
        roof_rise = float(params.get("roof_rise_mm", 25))
        result = unfold_building(
            width, depth, wall_h, roof_rise, flap_mm=flap
        )
        if markings:
            result = add_building_markings(result)
        title = f"Budynek {width:g}×{depth:g} mm (ściana {wall_h:g}, dach {roof_rise:g})"
    elif shape == "wagon":
        length = float(params.get("length_mm", params.get("width_mm", 100)))
        width = float(params.get("wagon_width_mm", params.get("depth_mm", 40)))
        height = float(params.get("height_mm", 35))
        chassis = float(params.get("chassis_height_mm", 8))
        wheel = float(params.get("wheel_diameter_mm", 18))
        result = unfold_wagon(
            length,
            width,
            height,
            chassis_height_mm=chassis,
            wheel_diameter_mm=wheel,
            flap_mm=flap,
        )
        if markings:
            result = add_wagon_markings(result)
        title = f"Wagon {length:g}×{width:g}×{height:g} mm"
    elif shape == "fighter":
        result = unfold_fighter(
            fuselage_length_mm=float(params.get("fuselage_length_mm", 200)),
            fuselage_diameter_mm=float(params.get("fuselage_diameter_mm", 28)),
            wingspan_mm=float(params.get("wingspan_mm", 230)),
            wing_chord_mm=float(params.get("wing_chord_mm", 38)),
            tailplane_span_mm=float(params.get("tailplane_span_mm", 70)),
            tailplane_chord_mm=float(params.get("tailplane_chord_mm", 22)),
            fin_height_mm=float(params.get("fin_height_mm", 32)),
            fin_chord_mm=float(params.get("fin_chord_mm", 28)),
            flap_mm=flap,
            stations=int(params.get("stations", 10)),
        )
        # główny arkusz = skóry (kolor); formers osobno
        from .fighter_unfold import split_formers_and_skins

        formers_split, skins_split = split_formers_and_skins(result)
        result = skins_split
        title = (
            f"Myśliwiec L={params.get('fuselage_length_mm', 200)} "
            f"span={params.get('wingspan_mm', 230)} mm"
        )
    else:
        return {"ok": False, "error": f"Unsupported shape: {shape}"}

    # Reguła mikro-części → podklejenie
    policy = PartPolicy(
        min_part_mm=float(params.get("min_part_mm", 6.0)),
        laminate_thickness_mm=float(params.get("former_thickness_mm", 1.0)),
    )
    part_analysis = analyze_parts(result, policy)
    result = apply_policy_notes(result, part_analysis)

    # Bitmapy schematu malowania (+ opcjonalna receptura z AI)
    textures = None
    scheme_key = params.get("paint_scheme") or params.get("scheme")
    paint_recipe = params.get("paint_recipe")
    if isinstance(paint_recipe, str):
        try:
            paint_recipe = json.loads(paint_recipe)
        except json.JSONDecodeError:
            paint_recipe = None
    if scheme_key:
        tex_dir = output_dir / "textures"
        textures = bake_scheme_textures(
            tex_dir,
            str(scheme_key),
            result.panels,
            paint_recipe=paint_recipe if isinstance(paint_recipe, dict) else None,
        )

    pages = pack_panels_to_sheets(
        result,
        sheet=sheet,
        force_multisheet=force_multi,
    )
    multisheet = len(pages) > 1

    svg_paths = write_svg_pages(
        pages,
        output_dir,
        sheet=sheet,
        title=title,
        style=style,
        multisheet=multisheet,
        recipe=recipe,
        textures=textures,
    )
    pdf_path = write_pdf_pages(
        pages,
        output_dir / "sheet.pdf",
        sheet=sheet,
        title=title,
        style=style,
        multisheet=multisheet,
    )

    instruction_path = None
    formers_svg_path = None
    formers_pdf_path = None

    if with_instructions:
        sw, sh = SHEETS[sheet]
        instr = build_instruction_page(result, title=title, sheet_w=sw, sheet_h=sh)
        instruction_path = output_dir / "instructions.svg"
        instruction_path.write_text(instr, encoding="utf-8")

    formers_result = None
    if with_formers:
        if shape == "box":
            formers_result = build_formers_for_box(
                float(params.get("width_mm", 80)),
                float(params.get("height_mm", 50)),
                float(params.get("depth_mm", 40)),
                thickness_mm=former_thickness,
            )
        elif shape == "building":
            formers_result = build_formers_for_building(
                float(params.get("width_mm", 80)),
                float(params.get("depth_mm", 60)),
                float(params.get("wall_height_mm", params.get("height_mm", 45))),
                float(params.get("roof_rise_mm", 25)),
                thickness_mm=former_thickness,
            )
        elif shape == "wagon":
            formers_result = build_formers_for_box(
                float(params.get("length_mm", params.get("width_mm", 100))),
                float(params.get("height_mm", 35)),
                float(params.get("wagon_width_mm", params.get("depth_mm", 40))),
                thickness_mm=former_thickness,
            )
        elif shape == "fighter":
            from .fighter_unfold import unfold_fighter as _uf, split_formers_and_skins

            full = _uf(
                fuselage_length_mm=float(params.get("fuselage_length_mm", 200)),
                fuselage_diameter_mm=float(params.get("fuselage_diameter_mm", 28)),
                wingspan_mm=float(params.get("wingspan_mm", 230)),
                wing_chord_mm=float(params.get("wing_chord_mm", 38)),
                flap_mm=flap,
                stations=int(params.get("stations", 10)),
            )
            formers_result, _skins = split_formers_and_skins(full)

        if formers_result is not None:
            f_pages = pack_panels_to_sheets(formers_result, sheet=sheet)
            f_svgs = write_svg_pages(
                f_pages,
                output_dir,
                sheet=sheet,
                title=f"Formierze — {title}",
                style="clean",
                multisheet=len(f_pages) > 1,
                basename="formers",
            )
            formers_svg_path = f_svgs[0]
            formers_pdf_path = write_pdf_pages(
                f_pages,
                output_dir / "formers.pdf",
                sheet=sheet,
                title=f"Formierze — {title}",
                style="clean",
            )

    sw, sh = SHEETS[sheet]
    return {
        "ok": True,
        "svg_path": str(svg_paths[0].resolve()),
        "svg_paths": [str(p.resolve()) for p in svg_paths],
        "pdf_path": str(pdf_path.resolve()),
        "instruction_svg_path": str(instruction_path.resolve()) if instruction_path else None,
        "formers_svg_path": str(formers_svg_path.resolve()) if formers_svg_path else None,
        "formers_pdf_path": str(formers_pdf_path.resolve()) if formers_pdf_path else None,
        "page_count": len(pages),
        "multisheet": multisheet,
        "markings": markings,
        "series": series,
        "scale": scale,
        "profile": profile,
        "style_recipe": recipe.to_dict(),
        "layers": {
            "parts": True,
            "instructions": bool(instruction_path),
            "formers": bool(formers_svg_path),
        },
        "style": style.key,
        "paint_scheme": scheme_key,
        "part_policy": part_analysis,
        "textures": [str(p) for p in (textures or {}).values()],
        "available_schemes": list_schemes() if shape == "fighter" else None,
        "parts": [
            {"id": p.id, "name": p.name, "label": p.label}
            for p in result.panels
        ],
        "instructions": result.instructions,
        "sheet": {"format": sheet, "width_mm": sw, "height_mm": sh},
        "net_size_mm": {
            "width": result.width_mm,
            "height": result.height_mm,
        },
    }


def analyze_from_payload(payload: dict) -> dict:
    image_path = Path(payload["image_path"])
    output_dir = Path(payload["output_dir"])
    max_lines = int(payload.get("max_lines", 80))
    return analyze_scan(image_path, output_dir, max_lines=max_lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="geometry_worker")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate cardboard net SVG+PDF")
    gen.add_argument("--input", required=True, help="Path to request JSON")

    ana = sub.add_parser("analyze", help="Analyze scan image (line suggestions)")
    ana.add_argument("--input", required=True, help="Path to request JSON")

    args = parser.parse_args(argv)

    if args.command == "generate":
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = generate_from_payload(payload)
        sys.stdout.write(json.dumps(result, ensure_ascii=False))
        sys.stdout.write("\n")
        return 0 if result.get("ok") else 1

    if args.command == "analyze":
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = analyze_from_payload(payload)
        sys.stdout.write(json.dumps(result, ensure_ascii=False))
        sys.stdout.write("\n")
        return 0 if result.get("ok") else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
