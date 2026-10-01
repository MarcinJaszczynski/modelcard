<?php

namespace App\Services\Research;

/**
 * Wyszukiwanie wzorca + schematy malowania (korpus + reguły).
 * Nie pobieramy cudzych plansz — tylko metadane schematów i referencje publiczne.
 */
class SubjectResearchService
{
    /**
     * @return array{
     *   query: string,
     *   subject: array<string, mixed>|null,
     *   schemes: list<array<string, mixed>>,
     *   kit_hints: list<string>,
     *   recommended_template: string|null,
     *   recommended_scale: string|null
     * }
     */
    public function search(string $query): array
    {
        $q = mb_strtolower(trim($query));
        $catalog = $this->catalog();

        $matches = [];
        foreach ($catalog as $item) {
            $hay = mb_strtolower(implode(' ', $item['keywords']));
            $score = 0;
            foreach (preg_split('/\s+/u', $q) ?: [] as $token) {
                if ($token !== '' && str_contains($hay, $token)) {
                    $score++;
                }
            }
            if ($score > 0) {
                $matches[] = ['score' => $score, 'item' => $item];
            }
        }

        usort($matches, fn ($a, $b) => $b['score'] <=> $a['score']);

        if ($matches === []) {
            return [
                'query' => $query,
                'subject' => null,
                'schemes' => [],
                'kit_hints' => [
                    'Brak dopasowania w korpusie — doprecyzuj (np. „p51 mustang korea”, „f-51 45th trs”).',
                ],
                'recommended_template' => null,
                'recommended_scale' => null,
            ];
        }

        $best = $matches[0]['item'];

        return [
            'query' => $query,
            'subject' => [
                'id' => $best['id'],
                'label' => $best['label'],
                'type' => $best['type'],
                'summary' => $best['summary'],
            ],
            'schemes' => $best['schemes'],
            'kit_hints' => $best['kit_hints'],
            'recommended_template' => $best['template'],
            'recommended_scale' => $best['scale'],
        ];
    }

    /**
     * @return list<array<string, mixed>>
     */
    private function catalog(): array
    {
        return [
            [
                'id' => 'f51_korea',
                'label' => 'North American F-51D / RF-51D Mustang (wojna koreańska)',
                'type' => 'fighter',
                'template' => 'p51_korea',
                'scale' => '1:48',
                'keywords' => [
                    'p51', 'p-51', 'f51', 'f-51', 'rf-51', 'mustang', 'korea',
                    'korean', '45th', 'trs', 'polka', 'kimpo', 'usaf',
                ],
                'summary' => 'Mustang w Korei zwykle w matowym aluminium lacquer (nie świeży NMF), '
                    .'często z kolorowymi oznaczeniami eskadr (np. 45th TRS polka dots).',
                'schemes' => [
                    [
                        'key' => 'korea_aluminum',
                        'label' => 'Aluminium lacquer (matowy srebrny) — typowy Korea',
                        'era' => '1950–53',
                        'notes' => 'Remontowane płatowce malowane matowym aluminium; silne zużycie.',
                        'refs' => [
                            'https://thescalemodelhangar.com/2021/06/29/the-f-51d-mustang-in-korea/',
                        ],
                    ],
                    [
                        'key' => 'korea_45ths_polka',
                        'label' => '45th TRS „Polka Dot” — niebieskie końcówki + białe kropki',
                        'era' => '~1952',
                        'notes' => 'Spinner/końcówki skrzydeł i usterzenia: blue + white polka dots.',
                        'refs' => [
                            'https://www.koreanwar.org/html/units/usaf/45trs.htm',
                            'https://modelingmadness.com/review/korean/cleaverrf51.htm',
                        ],
                    ],
                    [
                        'key' => 'korea_od_gray',
                        'label' => 'Olive Drab / Neutral Gray (styl przejściowy)',
                        'era' => 'wczesny / demonstracyjny',
                        'notes' => 'Rzadziej w Korei; przydatny jako wariant treningowy schematu.',
                        'refs' => [],
                    ],
                ],
                'kit_hints' => [
                    'Skala kartonowa typowa dla samolotów: 1:33 / 1:48 (u nas domyślnie 1:48).',
                    'Szukaj planów modelarskich jako inspiracji geometrii — nie kopiuj arkuszy wydawnictw.',
                    'Detale < 6 mm: podklej na tekturę 1 mm i wytnij (nie sklejaj mikro-kostek).',
                    'Warstwy: parts (0,2 mm) + formierze (1 mm) + bitmapy schematu.',
                ],
            ],
            [
                'id' => 'van_express',
                'label' => 'Furgon / van 1:25 (profil Express)',
                'type' => 'vehicle',
                'template' => 'van',
                'scale' => '1:25',
                'keywords' => ['van', 'furgon', 'vivaro', 'dostawczy', 'express'],
                'summary' => 'Uproszczony pojazd dostawczy — profil express.',
                'schemes' => [],
                'kit_hints' => ['Użyj modelu van bez schematu lotniczego.'],
            ],
        ];
    }
}
