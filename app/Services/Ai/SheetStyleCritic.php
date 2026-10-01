<?php

namespace App\Services\Ai;

/**
 * Krytyka stylu planszy względem checklisty wydawniczej + malowania.
 * Lokalna AI proponuje poprawki — geometria zostaje deterministyczna.
 */
class SheetStyleCritic
{
    public function __construct(private LocalAiClient $ai) {}

    /**
     * @param  array<string, mixed>  $generationResult
     * @param  array<string, mixed>  $parameters
     * @return array{ok: bool, score?: int, notes?: list<string>, recipe_tweaks?: array<string, mixed>, paint_tweaks?: array<string, mixed>, raw?: string}|null
     */
    public function critique(array $generationResult, array $parameters): ?array
    {
        if (! config('ai.critique_after_generate', true) || ! $this->ai->enabled()) {
            return null;
        }

        $recipe = $parameters['style_recipe'] ?? $generationResult['style_recipe'] ?? [];
        $profile = $parameters['profile'] ?? $generationResult['profile'] ?? 'express';
        $parts = count($generationResult['parts'] ?? []);
        $pages = (int) ($generationResult['page_count'] ?? 1);
        $layers = $generationResult['layers'] ?? [];
        $textures = $generationResult['textures'] ?? [];
        $paint = $parameters['paint_recipe'] ?? $generationResult['paint_scheme'] ?? null;

        $system = <<<'SYS'
Jesteś seniorem QC wycinanek kartonowych (Betexa/WAK/Modelik/GPM/JSC).
Oceń styl I malowanie planszy. Nie wymyślaj geometrii CAD.
Odpowiedz WYŁĄCZNIE JSON:
{"score":0-100,"notes":["..."],"recipe_tweaks":{"bleed_mm":number?,"panel_line_spacing_mm":number?,"rivet_spacing_mm":number?,"weathering_streaks":bool?,"show_part_labels":false},"paint_tweaks":{"anti_glare_nose":bool?,"exhaust_stains":bool?,"wing_walkways":bool?,"polka_tips":bool?}}
Kryteria: brak nazw części na farbie (tylko numery), aluminium nie flat-gray, anti-glare/exhaust/walkway gdy Korea NMF, canopy framed, insignia US.
SYS;

        $user = json_encode([
            'profile' => $profile,
            'style' => $generationResult['style'] ?? null,
            'style_recipe' => $recipe,
            'paint_scheme' => $generationResult['paint_scheme'] ?? $parameters['paint_scheme'] ?? null,
            'paint_recipe_present' => is_array($paint),
            'textures_count' => is_array($textures) ? count($textures) : 0,
            'parts_count' => $parts,
            'page_count' => $pages,
            'layers' => $layers,
            'checklist' => [
                'bleed_present' => true,
                'part_numbers' => true,
                'hide_name_labels' => ! ($recipe['show_part_labels'] ?? false),
                'cut_vs_fold_legend' => true,
                'panel_lines' => (bool) ($recipe['panel_lines'] ?? true),
                'weathering_logic' => (bool) ($recipe['weathering_streaks'] ?? false),
                'has_paint_bitmaps' => is_array($textures) && count($textures) > 0,
            ],
        ], JSON_UNESCAPED_UNICODE);

        $raw = $this->ai->chat($system, (string) $user);
        if ($raw === null || $raw === '') {
            return null;
        }

        $json = $this->extractJson($raw);
        if ($json === null) {
            return [
                'ok' => true,
                'raw' => $raw,
                'notes' => ['AI nie zwróciło poprawnego JSON — zapisano surową odpowiedź.'],
            ];
        }

        return [
            'ok' => true,
            'score' => (int) ($json['score'] ?? 0),
            'notes' => array_values($json['notes'] ?? []),
            'recipe_tweaks' => $json['recipe_tweaks'] ?? [],
            'paint_tweaks' => $json['paint_tweaks'] ?? [],
            'raw' => $raw,
        ];
    }

    /**
     * @return array<string, mixed>|null
     */
    private function extractJson(string $raw): ?array
    {
        $raw = trim($raw);
        if (str_starts_with($raw, '```')) {
            $raw = preg_replace('/^```(?:json)?\s*/i', '', $raw) ?? $raw;
            $raw = preg_replace('/\s*```$/', '', $raw) ?? $raw;
        }

        $decoded = json_decode($raw, true);
        if (is_array($decoded)) {
            return $decoded;
        }

        if (preg_match('/\{.*\}/s', $raw, $m)) {
            $decoded = json_decode($m[0], true);

            return is_array($decoded) ? $decoded : null;
        }

        return null;
    }
}
