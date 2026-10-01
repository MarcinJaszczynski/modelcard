"""StyleRecipe — konwencje wizualne wycinanki (nie kopia cudzych plansz).

Profile inspirowane rynkiem (Betexa/Express → WAK → Modelik → JSC → GPM),
ale z własnymi regułami: bleed, linie podziału, nity, modulacja, zacieki.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class StyleRecipe:
    profile: str = "express"
    bleed_mm: float = 0.7
    panel_lines: bool = True
    panel_line_spacing_mm: float = 16.0
    rivets: bool = True
    rivet_spacing_mm: float = 7.0
    color_modulation: bool = True
    weathering_streaks: bool = True
    part_numbers: bool = True
    glue_hatch: bool = True
    edge_darken: bool = True
    # Nazwy typu „Skrzydło L góra” na farbie — w prawdziwych kitach ich nie ma
    show_part_labels: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


PROFILES: dict[str, StyleRecipe] = {
    # Betexa 1–2 / Answer Express — czytelnie, umiarkowany detal
    "express": StyleRecipe(
        profile="express",
        bleed_mm=0.7,
        panel_line_spacing_mm=18.0,
        rivet_spacing_mm=8.0,
        rivets=True,
        weathering_streaks=True,
    ),
    # WAK zeszyt — gęstsze linie, wyraźniejsze numery
    "magazine": StyleRecipe(
        profile="magazine",
        bleed_mm=0.9,
        panel_line_spacing_mm=12.0,
        rivet_spacing_mm=6.0,
        rivets=True,
        weathering_streaks=True,
    ),
    # Modelik — więcej detalu konstrukcyjnego na poszyciu
    "workshop": StyleRecipe(
        profile="workshop",
        bleed_mm=1.0,
        panel_line_spacing_mm=10.0,
        rivet_spacing_mm=5.0,
        rivets=True,
        weathering_streaks=True,
    ),
    # JSC-like — gęsty nesting wizualnie (linie), mniej „fotograficznego” weatheringu
    "fleet_compact": StyleRecipe(
        profile="fleet_compact",
        bleed_mm=0.5,
        panel_line_spacing_mm=9.0,
        rivet_spacing_mm=5.5,
        rivets=True,
        weathering_streaks=False,
        color_modulation=True,
    ),
    # GPM high — bogaty detal
    "studio": StyleRecipe(
        profile="studio",
        bleed_mm=1.1,
        panel_line_spacing_mm=8.0,
        rivet_spacing_mm=4.5,
        rivets=True,
        weathering_streaks=True,
    ),
}

# Mapowanie starych serii → profil
SERIES_TO_PROFILE = {
    "beginner": "express",
    "standard": "magazine",
    "advanced": "studio",
}


def resolve_recipe(params: dict | None = None) -> StyleRecipe:
    params = params or {}
    if isinstance(params.get("style_recipe"), dict):
        raw = params["style_recipe"]
        base = PROFILES.get(str(raw.get("profile", "express")), PROFILES["express"])
        return StyleRecipe(
            profile=str(raw.get("profile", base.profile)),
            bleed_mm=float(raw.get("bleed_mm", base.bleed_mm)),
            panel_lines=bool(raw.get("panel_lines", base.panel_lines)),
            panel_line_spacing_mm=float(
                raw.get("panel_line_spacing_mm", base.panel_line_spacing_mm)
            ),
            rivets=bool(raw.get("rivets", base.rivets)),
            rivet_spacing_mm=float(raw.get("rivet_spacing_mm", base.rivet_spacing_mm)),
            color_modulation=bool(raw.get("color_modulation", base.color_modulation)),
            weathering_streaks=bool(
                raw.get("weathering_streaks", base.weathering_streaks)
            ),
            part_numbers=bool(raw.get("part_numbers", base.part_numbers)),
            glue_hatch=bool(raw.get("glue_hatch", base.glue_hatch)),
            edge_darken=bool(raw.get("edge_darken", base.edge_darken)),
            show_part_labels=bool(raw.get("show_part_labels", base.show_part_labels)),
        )

    profile = params.get("profile") or params.get("style_profile")
    if not profile:
        series = str(params.get("series", "beginner"))
        profile = SERIES_TO_PROFILE.get(series, "express")
    return PROFILES.get(str(profile), PROFILES["express"])
