<?php

/**
 * Konwencje produkcyjne inspirowane rynkiem wycinanek (m.in. Answer),
 * bez kopiowania cudzych plansz — tylko zasady warsztatowe.
 */
return [
    /*
    | Typowe skale wydawnicze (realny świat → model).
    */
    'scales' => [
        '1:25' => ['ratio' => 25, 'typical' => ['vehicle', 'wagon'], 'label' => '1:25 (pojazdy)'],
        '1:33' => ['ratio' => 33, 'typical' => ['aircraft'], 'label' => '1:33 (samoloty)'],
        '1:50' => ['ratio' => 50, 'typical' => ['aircraft'], 'label' => '1:50'],
        '1:87' => ['ratio' => 87, 'typical' => ['railway'], 'label' => '1:87 H0 (kolej)'],
        '1:100' => ['ratio' => 100, 'typical' => ['ship'], 'label' => '1:100 (okręty)'],
        '1:200' => ['ratio' => 200, 'typical' => ['ship'], 'label' => '1:200 (okręty)'],
    ],

    /*
    | Serie trudności (legacy) — mapowane na profile wydawnicze.
    */
    'series' => [
        'beginner' => [
            'label' => 'Początkujący (styl Express)',
            'preferred_sheet' => 'A4',
            'target_pages' => [1, 4],
            'markings_default' => true,
            'formers_default' => false,
            'profile' => 'express',
        ],
        'standard' => [
            'label' => 'Standard (styl zeszytowy)',
            'preferred_sheet' => 'A4',
            'target_pages' => [2, 12],
            'markings_default' => true,
            'formers_default' => true,
            'profile' => 'magazine',
        ],
        'advanced' => [
            'label' => 'Zaawansowany (styl studio)',
            'preferred_sheet' => 'A3',
            'target_pages' => [8, 80],
            'markings_default' => true,
            'formers_default' => true,
            'profile' => 'studio',
        ],
    ],

    /*
    | Profile wizualne / konstrukcyjne (inspiracja Betexa→WAK→Modelik→JSC→GPM).
    | Sterują StyleRecipe w workerze — nie kopiują cudzych plansz.
    */
    'profiles' => [
        'express' => [
            'label' => 'Express (czytelny, mało arkuszy)',
            'style_recipe' => [
                'profile' => 'express',
                'bleed_mm' => 0.7,
                'panel_lines' => true,
                'panel_line_spacing_mm' => 18.0,
                'rivets' => true,
                'rivet_spacing_mm' => 8.0,
                'color_modulation' => true,
                'weathering_streaks' => true,
                'part_numbers' => true,
                'glue_hatch' => true,
                'edge_darken' => true,
            ],
        ],
        'magazine' => [
            'label' => 'Magazine (zeszyt, gęstszy detal)',
            'style_recipe' => [
                'profile' => 'magazine',
                'bleed_mm' => 0.9,
                'panel_lines' => true,
                'panel_line_spacing_mm' => 12.0,
                'rivets' => true,
                'rivet_spacing_mm' => 6.0,
                'color_modulation' => true,
                'weathering_streaks' => true,
                'part_numbers' => true,
                'glue_hatch' => true,
                'edge_darken' => true,
            ],
        ],
        'workshop' => [
            'label' => 'Workshop (rama + oklejki)',
            'style_recipe' => [
                'profile' => 'workshop',
                'bleed_mm' => 1.0,
                'panel_lines' => true,
                'panel_line_spacing_mm' => 10.0,
                'rivets' => true,
                'rivet_spacing_mm' => 5.0,
                'color_modulation' => true,
                'weathering_streaks' => true,
                'part_numbers' => true,
                'glue_hatch' => true,
                'edge_darken' => true,
            ],
        ],
        'fleet_compact' => [
            'label' => 'Fleet compact (gęsty nesting)',
            'style_recipe' => [
                'profile' => 'fleet_compact',
                'bleed_mm' => 0.5,
                'panel_lines' => true,
                'panel_line_spacing_mm' => 9.0,
                'rivets' => true,
                'rivet_spacing_mm' => 5.5,
                'color_modulation' => true,
                'weathering_streaks' => false,
                'part_numbers' => true,
                'glue_hatch' => true,
                'edge_darken' => true,
            ],
        ],
        'studio' => [
            'label' => 'Studio (bogaty detal)',
            'style_recipe' => [
                'profile' => 'studio',
                'bleed_mm' => 1.1,
                'panel_lines' => true,
                'panel_line_spacing_mm' => 8.0,
                'rivets' => true,
                'rivet_spacing_mm' => 4.5,
                'color_modulation' => true,
                'weathering_streaks' => true,
                'part_numbers' => true,
                'glue_hatch' => true,
                'edge_darken' => true,
            ],
        ],
    ],

    'default_profile' => 'express',

    /*
    | Warstwy produktu wycinanki.
    */
    'layers' => [
        'parts' => 'Arkusze części (druk 0,2 mm)',
        'instructions' => 'Rysunki montażowe',
        'formers' => 'Formierze / szkielet (tektura grubsza)',
    ],

    /*
    | Grubości materiału (mm) — ekosystem Answer-like.
    */
    'materials' => [
        'print' => 0.2,
        'former_thin' => 0.5,
        'former' => 1.0,
        'former_thick' => 1.5,
        'former_heavy' => 2.0,
    ],

    'default_series' => 'beginner',
    'default_scale' => '1:25',

    /*
    | Szablony automatyki — realne wymiary w mm (obiekt), generator przeliczy skalą.
    | real_* = wymiary obiektu w rzeczywistości [mm] albo już modelowe jeśli scale_locked.
    */
    'templates' => [
        'van' => [
            'label' => 'Furgon / van',
            'shape' => 'box',
            'category_group' => 'vehicle',
            'default_scale' => '1:25',
            'default_series' => 'beginner',
            // wymiary modelu w mm przy skali 1:25 (Express-like)
            'model_mm' => [
                'width_mm' => 180,
                'height_mm' => 90,
                'depth_mm' => 80,
            ],
            'style' => 'dirt',
            'markings' => true,
            'markings_profile' => 'vehicle',
            'instructions' => true,
            'formers' => true,
            'sheet' => 'A4',
        ],
        'tractor' => [
            'label' => 'Ciągnik (uproszczony)',
            'shape' => 'box',
            'category_group' => 'vehicle',
            'default_scale' => '1:25',
            'default_series' => 'beginner',
            'model_mm' => [
                'width_mm' => 120,
                'height_mm' => 70,
                'depth_mm' => 60,
            ],
            'style' => 'dirt',
            'markings' => true,
            'markings_profile' => 'vehicle',
            'instructions' => true,
            'formers' => true,
            'sheet' => 'A4',
        ],
        'house' => [
            'label' => 'Domek / budynek',
            'shape' => 'building',
            'category_group' => 'building',
            'default_scale' => '1:25',
            'default_series' => 'beginner',
            'model_mm' => [
                'width_mm' => 100,
                'depth_mm' => 70,
                'wall_height_mm' => 50,
                'roof_rise_mm' => 28,
            ],
            'style' => 'clean',
            'markings' => true,
            'markings_profile' => 'building',
            'instructions' => true,
            'formers' => true,
            'sheet' => 'A4',
        ],
        'freight_wagon' => [
            'label' => 'Wagon towarowy',
            'shape' => 'wagon',
            'category_group' => 'railway',
            'default_scale' => '1:87',
            'default_series' => 'beginner',
            'model_mm' => [
                'length_mm' => 110,
                'wagon_width_mm' => 36,
                'height_mm' => 32,
                'chassis_height_mm' => 7,
                'wheel_diameter_mm' => 14,
            ],
            'style' => 'rust',
            'markings' => true,
            'markings_profile' => 'wagon',
            'instructions' => true,
            'formers' => true,
            'sheet' => 'A4',
        ],
        'silo' => [
            'label' => 'Silos / zbiornik',
            'shape' => 'cylinder',
            'category_group' => 'industrial',
            'default_scale' => '1:25',
            'default_series' => 'beginner',
            'model_mm' => [
                'diameter_mm' => 55,
                'height_mm' => 100,
                'segments' => 24,
            ],
            'style' => 'dust',
            'markings' => false,
            'markings_profile' => null,
            'instructions' => true,
            'formers' => false,
            'sheet' => 'A4',
        ],
        'crate' => [
            'label' => 'Skrzynia',
            'shape' => 'box',
            'category_group' => 'props',
            'default_scale' => '1:25',
            'default_series' => 'beginner',
            'model_mm' => [
                'width_mm' => 60,
                'height_mm' => 40,
                'depth_mm' => 40,
            ],
            'style' => 'clean',
            'markings' => false,
            'markings_profile' => null,
            'instructions' => true,
            'formers' => false,
            'sheet' => 'A4',
        ],
        'p51_korea' => [
            'label' => 'F-51D Mustang (Korea)',
            'shape' => 'fighter',
            'category_group' => 'aircraft',
            'default_scale' => '1:48',
            'default_series' => 'standard',
            'profile' => 'magazine',
            // wymiary modelu ~1:48
            'model_mm' => [
                'fuselage_length_mm' => 205,
                'fuselage_diameter_mm' => 26,
                'wingspan_mm' => 235,
                'wing_chord_mm' => 36,
                'tailplane_span_mm' => 72,
                'tailplane_chord_mm' => 20,
                'fin_height_mm' => 30,
                'fin_chord_mm' => 26,
            ],
            'style' => 'dust',
            'markings' => false,
            'markings_profile' => null,
            'paint_scheme' => 'korea_45ths_polka',
            'instructions' => true,
            'formers' => true,
            'sheet' => 'A4',
            'min_part_mm' => 6.0,
        ],
    ],

    /*
    | Minimalny wymiar części drukowanej — poniżej: podklej i wytnij.
    */
    'min_part_mm' => 6.0,
];
