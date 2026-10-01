<?php

namespace App\Services\Geometry;

use App\Enums\ModelCategory;
use App\Enums\PrimitiveShape;
use InvalidArgumentException;

class ModelTemplateLibrary
{
    /**
     * @return array{shape: PrimitiveShape, parameters: array<string, mixed>, meta: array<string, mixed>}
     */
    public function resolve(
        ModelCategory|string $category,
        ?string $scale = null,
        ?string $series = null,
        ?string $style = null,
        ?float $sizeFactor = null,
    ): array {
        $key = $category instanceof ModelCategory ? $category->value : $category;
        $templates = config('modelarz.templates', []);

        if (! isset($templates[$key])) {
            throw new InvalidArgumentException("Nieznany szablon kategorii: {$key}");
        }

        $tpl = $templates[$key];
        $shape = PrimitiveShape::from($tpl['shape']);
        $scale ??= $tpl['default_scale'] ?? config('modelarz.default_scale');
        $series ??= $tpl['default_series'] ?? config('modelarz.default_series');
        $seriesMeta = config("modelarz.series.{$series}", config('modelarz.series.beginner'));
        $profile = $tpl['profile']
            ?? ($seriesMeta['profile'] ?? null)
            ?? config('modelarz.default_profile', 'express');
        $recipe = config("modelarz.profiles.{$profile}.style_recipe")
            ?? config('modelarz.profiles.express.style_recipe');

        $params = array_merge($tpl['model_mm'] ?? [], [
            'flap_mm' => 8.0,
            'sheet' => $seriesMeta['preferred_sheet'] ?? ($tpl['sheet'] ?? 'A4'),
            'style' => $style ?? ($tpl['style'] ?? 'clean'),
            'markings' => (bool) ($tpl['markings'] ?? $seriesMeta['markings_default'] ?? true),
            'markings_profile' => $tpl['markings_profile'] ?? null,
            'paint_scheme' => $tpl['paint_scheme'] ?? null,
            'min_part_mm' => (float) ($tpl['min_part_mm'] ?? config('modelarz.min_part_mm', 6.0)),
            'instructions' => (bool) ($tpl['instructions'] ?? true),
            'formers' => (bool) ($tpl['formers'] ?? $seriesMeta['formers_default'] ?? false),
            'former_thickness_mm' => (float) config('modelarz.materials.former', 1.0),
            'multisheet' => false,
            'series' => $series,
            'scale' => $scale,
            'auto' => true,
            'template' => $key,
            'profile' => $profile,
            'style_recipe' => $recipe,
        ]);

        // lekka korekta rozmiaru (np. z CV aspect / preferencji użytkownika)
        $factor = $sizeFactor ?? 1.0;
        $factor = max(0.6, min(1.6, $factor));
        foreach (['width_mm', 'height_mm', 'depth_mm', 'length_mm', 'wagon_width_mm', 'diameter_mm', 'wall_height_mm', 'roof_rise_mm', 'fuselage_length_mm', 'fuselage_diameter_mm', 'wingspan_mm', 'wing_chord_mm', 'tailplane_span_mm', 'tailplane_chord_mm', 'fin_height_mm', 'fin_chord_mm'] as $dim) {
            if (isset($params[$dim]) && is_numeric($params[$dim])) {
                $params[$dim] = round(((float) $params[$dim]) * $factor, 1);
            }
        }

        return [
            'shape' => $shape,
            'parameters' => $params,
            'meta' => [
                'label' => $tpl['label'] ?? $key,
                'category_group' => $tpl['category_group'] ?? null,
                'size_factor' => $factor,
                'profile' => $profile,
            ],
        ];
    }

    /**
     * @return array<string, string>
     */
    public function options(): array
    {
        return collect(config('modelarz.templates', []))
            ->mapWithKeys(fn (array $tpl, string $key) => [$key => $tpl['label'] ?? $key])
            ->all();
    }
}
