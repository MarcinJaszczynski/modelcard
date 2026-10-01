<?php

namespace App\Services\Ai;

/**
 * Lokalna AI proponuje recepturę malowania planszy (nie geometrię CAD).
 * Wynik jest JSON-em konsumowanym przez geometry-worker / texture_bake.
 */
class PaintSchemeAdvisor
{
    public function __construct(private LocalAiClient $ai) {}

    /**
     * @param  array<string, mixed>  $context  query, scheme_key, scheme_label, notes…
     * @return array<string, mixed>|null
     */
    public function advise(array $context): ?array
    {
        if (! $this->ai->enabled()) {
            return null;
        }

        $system = <<<'SYS'
Jesteś seniorem malowań modeli kartonowych samolotów (P-51/F-51 Korea).
Nie kopiuj cudzych plansz. Zwróć TYLKO JSON receptury farby do generatora bitmap.
Format:
{"base_finish":"aluminum_matte|od_gray","panel_modulation":true,"anti_glare_nose":true,"exhaust_stains":true,"wing_walkways":true,"us_insignia":{"wing_upper":true,"fuse_rear":true},"polka_tips":bool,"canopy":"framed_glass","serial_style":"buzz_number","buzz_number":"FT-xxx","colors":{"aluminum":[r,g,b],"aluminum_shade":[r,g,b],"aluminum_hi":[r,g,b],"anti_glare":[r,g,b],"exhaust":[r,g,b],"walkway":[r,g,b],"glass":[r,g,b,a],"frame":[r,g,b],"accent_blue":[r,g,b],"od":[r,g,b],"neutral_gray":[r,g,b]}}
Kolory aluminium: chłodne srebrne (nie flat gray 190). Anti-glare ciemna oliwka/czerń. Accent_blue dla 45th TRS ~navy.
SYS;

        $user = json_encode($context, JSON_UNESCAPED_UNICODE);
        $raw = $this->ai->chat($system, (string) $user);
        if ($raw === null || $raw === '') {
            return null;
        }

        return $this->extractJson($raw);
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
