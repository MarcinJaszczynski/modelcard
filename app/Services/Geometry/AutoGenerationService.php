<?php

namespace App\Services\Geometry;

use App\Enums\AssetType;
use App\Enums\ModelCategory;
use App\Enums\PrimitiveShape;
use App\Enums\ProjectStatus;
use App\Models\CardboardProject;
use App\Models\GenerationJob;
use App\Models\ProjectAsset;
use App\Models\User;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Storage;
use Livewire\Features\SupportFileUploads\TemporaryUploadedFile;

/**
 * Maksymalnie automatyczny pipeline:
 * kategoria (+ opcjonalna referencja) → szablon → CV (opcjonalnie) → generacja wszystkich warstw.
 *
 * Decyzja architektoniczna: nie próbujemy full photo→CAD. Deterministyczny szablon
 * + lekka korekta CV (aspect/linie) daje powtarzalny, utrzymywalny zestaw wycinanki.
 */
class AutoGenerationService
{
    public function __construct(
        private ModelTemplateLibrary $templates,
        private GenerationDispatcher $dispatcher,
        private ScanAnalysisService $scanAnalysis,
    ) {}

    /**
     * @param  array{
     *   category: string,
     *   scale?: string|null,
     *   series?: string|null,
     *   style?: string|null,
     *   name?: string|null,
     *   analyze_reference?: bool,
     *   auto_detect_category?: bool,
     *   reference?: UploadedFile|TemporaryUploadedFile|string|null,
     *   project?: CardboardProject|null,
     *   size_factor?: float|null,
     *   paint_scheme?: string|null
     * }  $input
     * @return array{
     *   project: CardboardProject,
     *   job: GenerationJob,
     *   resolved: array,
     *   analysis: array|null
     * }
     */
    public function run(array $input): array
    {
        $category = ModelCategory::from($input['category']);
        $analyze = (bool) ($input['analyze_reference'] ?? true);
        $autoDetect = (bool) ($input['auto_detect_category'] ?? false);
        $sizeFactor = $input['size_factor'] ?? null;
        $analysis = null;

        $project = $input['project'] ?? $this->createProjectShell($category, $input['name'] ?? null);

        if (($input['reference'] ?? null) !== null) {
            $this->attachReference($project, $input['reference']);
        }

        if ($analyze || $autoDetect) {
            $analysis = $this->maybeAnalyzeAndAdjust($project, $sizeFactor, $autoDetect);
            if ($analysis && isset($analysis['size_factor'])) {
                $sizeFactor = $analysis['size_factor'];
            }
            if ($autoDetect && ! empty($analysis['suggested_category'])) {
                $category = ModelCategory::from($analysis['suggested_category']);
            }
        }

        $resolved = $this->templates->resolve(
            $category,
            $input['scale'] ?? null,
            $input['series'] ?? null,
            $input['style'] ?? null,
            $sizeFactor,
        );

        if (! empty($input['paint_scheme'])) {
            $resolved['parameters']['paint_scheme'] = $input['paint_scheme'];
        }

        $project->update([
            'name' => $input['name'] ?: ($resolved['meta']['label'].' auto '.now()->format('Y-m-d H:i')),
            'shape' => $resolved['shape'],
            'scale' => $resolved['parameters']['scale'] ?? null,
            'model_type' => $category->value,
            'status' => ProjectStatus::Ready,
            'parameters' => $resolved['parameters'],
            'description' => 'Wygenerowane automatycznie (szablon: '.$category->value
                .(! empty($resolved['parameters']['paint_scheme'])
                    ? ', schemat: '.$resolved['parameters']['paint_scheme']
                    : '')
                .')',
        ]);

        $job = $this->dispatcher->dispatchSync($project->fresh(), $resolved['parameters']);

        return [
            'project' => $project->fresh(),
            'job' => $job,
            'resolved' => $resolved,
            'analysis' => $analysis,
        ];
    }

    private function createProjectShell(ModelCategory $category, ?string $name): CardboardProject
    {
        /** @var User|null $user */
        $user = Auth::user();

        return CardboardProject::query()->create([
            'user_id' => $user?->id,
            'name' => $name ?: 'Auto '.$category->label(),
            'description' => null,
            'status' => ProjectStatus::Draft,
            'shape' => PrimitiveShape::Box,
            'parameters' => [],
            'model_type' => $category->value,
        ]);
    }

    private function attachReference(
        CardboardProject $project,
        UploadedFile|TemporaryUploadedFile|string $file,
    ): ProjectAsset {
        if (is_string($file)) {
            $path = $file;
            if (! Storage::disk('local')->exists($path)) {
                // ścieżka absolutna (CLI) → skopiuj do storage
                if (is_file($file)) {
                    $path = 'references/auto/'.basename($file);
                    Storage::disk('local')->put($path, file_get_contents($file));
                } else {
                    throw new \InvalidArgumentException("Referencja nie istnieje: {$file}");
                }
            }

            return ProjectAsset::query()->create([
                'cardboard_project_id' => $project->id,
                'type' => AssetType::Reference,
                'disk' => 'local',
                'path' => $path,
                'original_name' => basename($path),
                'mime_type' => mime_content_type(Storage::disk('local')->path($path)) ?: 'application/octet-stream',
                'size_bytes' => Storage::disk('local')->size($path),
                'tags' => ['auto', 'reference'],
                'annotation' => 'Referencja do automatyki generacji',
            ]);
        }

        $path = $file->store('references/auto', 'local');

        return ProjectAsset::query()->create([
            'cardboard_project_id' => $project->id,
            'type' => AssetType::Reference,
            'disk' => 'local',
            'path' => $path,
            'original_name' => method_exists($file, 'getClientOriginalName')
                ? $file->getClientOriginalName()
                : basename($path),
            'mime_type' => method_exists($file, 'getMimeType')
                ? $file->getMimeType()
                : null,
            'size_bytes' => method_exists($file, 'getSize') ? $file->getSize() : null,
            'tags' => ['auto', 'reference'],
            'annotation' => 'Referencja do automatyki generacji',
        ]);
    }

    /**
     * @return array{
     *   size_factor: float,
     *   overlay_asset_id?: int,
     *   line_count?: int,
     *   aspect?: float,
     *   suggested_category?: string|null,
     *   note?: string|null
     * }|null
     */
    private function maybeAnalyzeAndAdjust(
        CardboardProject $project,
        ?float $existingFactor,
        bool $suggestCategory = false,
    ): ?array {
        $asset = $project->assets()
            ->whereIn('type', [
                AssetType::Reference->value,
                AssetType::Scan->value,
                AssetType::Photo->value,
                AssetType::Drawing->value,
            ])
            ->latest('id')
            ->first();

        if (! $asset || ! Storage::disk($asset->disk)->exists($asset->path)) {
            // Brak referencji — size_factor zostaje z inputu; nie udajemy analizy CV.
            return null;
        }

        try {
            $out = $this->scanAnalysis->analyze($asset);
            $lineCount = (int) ($out['result']['line_count'] ?? 0);
            $image = $out['result']['image_size'] ?? [];
            $w = max(1, (int) ($image['width'] ?? 1));
            $h = max(1, (int) ($image['height'] ?? 1));
            $aspect = $w / $h;

            $factor = $existingFactor ?? 1.0;
            if ($aspect >= 1.6) {
                $factor *= 1.15;
            } elseif ($aspect <= 0.85) {
                $factor *= 0.9;
            }

            if ($lineCount > 40) {
                $factor *= 1.08;
            }

            $suggested = $suggestCategory
                ? $this->suggestCategoryFromAspect($aspect, $lineCount)
                : null;

            return [
                'size_factor' => round(max(0.6, min(1.6, $factor)), 3),
                'overlay_asset_id' => $out['overlay']->id,
                'line_count' => $lineCount,
                'aspect' => round($aspect, 3),
                'suggested_category' => $suggested?->value,
                'note' => $out['result']['note'] ?? null,
            ];
        } catch (\Throwable) {
            return $existingFactor ? ['size_factor' => $existingFactor] : null;
        }
    }

    /**
     * Heurystyka (nie ML): aspect ratio + gęstość linii → kategoria szablonu.
     * Stabilna i przewidywalna — użytkownik może zawsze nadpisać kategorię ręcznie.
     */
    private function suggestCategoryFromAspect(float $aspect, int $lineCount): ModelCategory
    {
        if ($aspect >= 2.2) {
            return ModelCategory::FreightWagon;
        }

        if ($aspect >= 1.55) {
            return ModelCategory::Van;
        }

        if ($aspect <= 0.75) {
            return ModelCategory::Silo;
        }

        if ($aspect >= 0.9 && $aspect <= 1.35 && $lineCount >= 25) {
            return ModelCategory::House;
        }

        if ($aspect < 1.2) {
            return ModelCategory::Crate;
        }

        return ModelCategory::Tractor;
    }
}
