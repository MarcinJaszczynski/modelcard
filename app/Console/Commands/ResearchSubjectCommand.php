<?php

namespace App\Console\Commands;

use App\Enums\GenerationJobStatus;
use App\Models\User;
use App\Services\Geometry\AutoGenerationService;
use App\Services\Research\SubjectResearchService;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Auth;

class ResearchSubjectCommand extends Command
{
    protected $signature = 'modelarz:research
        {query : np. \"p51 mustang korea\"}
        {--scheme= : Klucz schematu malowania (po wyszukaniu)}
        {--generate : Od razu wygeneruj wycinankę}
        {--scale= : Nadpisz skalę}
        {--list-schemes : Pokaż tylko schematy z wyniku}';

    protected $description = 'Wyszukaj wzorzec + schematy malowania; opcjonalnie generuj oteksturowaną wycinankę';

    public function handle(SubjectResearchService $research, AutoGenerationService $auto): int
    {
        $query = (string) $this->argument('query');
        $result = $research->search($query);

        if (! $result['subject']) {
            $this->error($result['kit_hints'][0] ?? 'Brak wyników');

            return self::FAILURE;
        }

        $this->info($result['subject']['label']);
        $this->line($result['subject']['summary']);
        $this->newLine();
        $this->line('Szablon: '.$result['recommended_template'].' · skala: '.$result['recommended_scale']);
        $this->newLine();
        $this->line('Schematy malowania:');

        foreach ($result['schemes'] as $i => $scheme) {
            $this->line(sprintf(
                '  [%d] %s  (key=%s)',
                $i + 1,
                $scheme['label'],
                $scheme['key'],
            ));
            $this->line('      '.$scheme['notes']);
            foreach ($scheme['refs'] ?? [] as $ref) {
                $this->line('      ref: '.$ref);
            }
        }

        $this->newLine();
        $this->line('Wskazówki montażu / plansz:');
        foreach ($result['kit_hints'] as $hint) {
            $this->line('  • '.$hint);
        }

        if ($this->option('list-schemes') || ! $this->option('generate')) {
            if (! $this->option('generate')) {
                $this->newLine();
                $this->comment('Aby wygenerować: php artisan modelarz:research "..." --scheme=KEY --generate');
            }

            return self::SUCCESS;
        }

        $scheme = $this->option('scheme') ?: ($result['schemes'][0]['key'] ?? null);
        $template = $result['recommended_template'];
        if (! $template) {
            $this->error('Brak recommended_template');

            return self::FAILURE;
        }

        $user = User::query()->first();
        if ($user) {
            Auth::login($user);
        }

        $this->info("Generuję: {$template} / schemat={$scheme} …");

        $gen = $auto->run([
            'category' => $template,
            'scale' => $this->option('scale') ?: $result['recommended_scale'],
            'paint_scheme' => $scheme,
            'name' => $result['subject']['label'].' / '.$scheme,
            'analyze_reference' => false,
        ]);

        $job = $gen['job'];
        if ($job->status !== GenerationJobStatus::Succeeded) {
            $this->error($job->error_message ?? 'Generacja nie powiodła się');

            return self::FAILURE;
        }

        $this->info('OK — projekt #'.$gen['project']->id);
        $this->line('SVG: '.$job->output_svg_path);
        $policy = $job->result_payload['part_policy'] ?? null;
        if ($policy) {
            $this->line(sprintf(
                'Part policy: ok=%s, laminate=%s (min %s mm)',
                $policy['ok_count'] ?? '?',
                $policy['laminate_count'] ?? '?',
                $policy['min_part_mm'] ?? '?',
            ));
        }
        $textures = $job->result_payload['textures'] ?? [];
        $this->line('Bitmapy: '.count($textures));

        return self::SUCCESS;
    }
}
