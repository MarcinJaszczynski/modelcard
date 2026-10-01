<?php

namespace App\Console\Commands;

use App\Enums\GenerationJobStatus;
use App\Enums\ModelCategory;
use App\Models\User;
use App\Services\Geometry\AutoGenerationService;
use App\Services\Geometry\ModelTemplateLibrary;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Auth;

class AutoGenerateCommand extends Command
{
    protected $signature = 'modelarz:auto
        {category? : Klucz szablonu (van|tractor|house|freight_wagon|silo|crate)}
        {--list : Pokaż dostępne szablony}
        {--scale= : Nadpisz skalę (np. 1:25)}
        {--series= : beginner|standard|advanced}
        {--style= : clean|dirt|rust|dust}
        {--name= : Nazwa projektu}
        {--reference= : Ścieżka do zdjęcia/skanu}
        {--analyze=1 : 1/0 analiza CV referencji}
        {--auto-category=0 : 1/0 zasugeruj kategorię z CV}
        {--size-factor=1 : Współczynnik rozmiaru 0.6–1.6}';

    protected $description = 'Maksymalnie automatyczne tworzenie zestawu: szablon → (CV) → SVG/PDF/instrukcja/formierze';

    public function handle(AutoGenerationService $auto, ModelTemplateLibrary $templates): int
    {
        if ($this->option('list')) {
            foreach ($templates->options() as $key => $label) {
                $this->line("  {$key} — {$label}");
            }

            return self::SUCCESS;
        }

        $category = $this->argument('category');
        if (! $category) {
            $this->error('Podaj kategorię albo użyj --list. Przykład: php artisan modelarz:auto van');

            return self::FAILURE;
        }

        if (! ModelCategory::tryFrom($category)) {
            $this->error("Nieznana kategoria: {$category}. Użyj --list.");

            return self::FAILURE;
        }

        $user = User::query()->first();
        if ($user) {
            Auth::login($user);
        }

        $reference = $this->option('reference');
        if (is_string($reference) && $reference !== '' && ! is_file($reference)) {
            $this->error("Plik referencji nie istnieje: {$reference}");

            return self::FAILURE;
        }

        $this->info('Uruchamiam auto-pipeline…');

        $result = $auto->run([
            'category' => $category,
            'scale' => $this->option('scale') ?: null,
            'series' => $this->option('series') ?: null,
            'style' => $this->option('style') ?: null,
            'name' => $this->option('name') ?: null,
            'analyze_reference' => filter_var($this->option('analyze'), FILTER_VALIDATE_BOOLEAN),
            'auto_detect_category' => filter_var($this->option('auto-category'), FILTER_VALIDATE_BOOLEAN),
            'size_factor' => (float) $this->option('size-factor'),
            'reference' => $reference ?: null,
        ]);

        $job = $result['job'];
        if ($job->status !== GenerationJobStatus::Succeeded) {
            $this->error($job->error_message ?? 'Generowanie nie powiodło się');

            return self::FAILURE;
        }

        $project = $result['project'];
        $meta = $result['resolved']['meta'];

        $this->info('OK — projekt #'.$project->id.' ('.$meta['label'].')');
        $this->line('Szablon: '.$project->model_type.' | kształt: '.$project->shape?->value);
        $this->line('Skala: '.($project->scale ?? '—').' | factor: '.($meta['size_factor'] ?? 1));
        $this->line('SVG: '.$job->output_svg_path);
        $this->line('PDF: '.$job->output_pdf_path);

        $layers = $job->result_payload['layers'] ?? [];
        if ($layers) {
            $this->line('Warstwy: '.json_encode($layers, JSON_UNESCAPED_UNICODE));
        }

        if ($analysis = $result['analysis']) {
            $this->line(sprintf(
                'CV: aspect=%s, linii=%s, factor=%s%s',
                $analysis['aspect'] ?? '—',
                $analysis['line_count'] ?? '—',
                $analysis['size_factor'] ?? '—',
                isset($analysis['suggested_category']) ? ', sugestia='.$analysis['suggested_category'] : '',
            ));
        }

        return self::SUCCESS;
    }
}
