<?php

namespace App\Jobs;

use App\Enums\AssetType;
use App\Enums\GenerationJobStatus;
use App\Enums\ProjectStatus;
use App\Models\GenerationJob;
use App\Models\ProjectAsset;
use App\Services\Ai\PaintSchemeAdvisor;
use App\Services\Ai\SheetStyleCritic;
use App\Services\Geometry\GeometryWorkerClient;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Storage;
use Throwable;

class ProcessGenerationJob implements ShouldQueue
{
    use Queueable;

    public function __construct(public GenerationJob $generationJob) {}

    public function handle(
        GeometryWorkerClient $client,
        SheetStyleCritic $critic,
        PaintSchemeAdvisor $paintAdvisor,
    ): void
    {
        $job = $this->generationJob->fresh();
        $project = $job->project;

        $job->update([
            'status' => GenerationJobStatus::Running,
            'started_at' => now(),
            'error_message' => null,
        ]);

        $project->update(['status' => ProjectStatus::Generating]);

        $relativeDir = trim(config('geometry.output_directory'), '/').'/'.$job->uuid;
        $absoluteDir = Storage::disk(config('geometry.output_disk'))->path($relativeDir);

        $params = $job->request_payload ?? [];
        if (! isset($params['style_recipe'])) {
            $profile = $params['profile'] ?? config('modelarz.default_profile', 'express');
            $params['profile'] = $profile;
            $params['style_recipe'] = config("modelarz.profiles.{$profile}.style_recipe")
                ?? config('modelarz.profiles.express.style_recipe');
        }

        // AI: receptura malowania przed bake bitmap (fighter + schemat)
        if (
            empty($params['paint_recipe'])
            && ! empty($params['paint_scheme'])
            && ($job->shape->value ?? null) === 'fighter'
        ) {
            $advice = $paintAdvisor->advise([
                'scheme_key' => $params['paint_scheme'],
                'subject' => $project->name,
                'model_type' => $project->model_type,
                'goal' => 'plansza wycinanki F-51 Korea — prawdziwe malowanie, bez napisów nazw na farbie',
            ]);
            if (is_array($advice) && $advice !== []) {
                $params['paint_recipe'] = $advice;
            }
        }

        // Bez nazw części na powierzchni druku gdy jest schemat
        if (! empty($params['paint_scheme'])) {
            $params['style_recipe'] = array_merge(
                $params['style_recipe'] ?? [],
                ['show_part_labels' => false],
            );
        }

        $payload = [
            'job_uuid' => $job->uuid,
            'shape' => $job->shape->value,
            'parameters' => $params,
            'output_dir' => $absoluteDir,
        ];

        $result = $client->generate($payload);

        $svgAbsolute = $result['svg_path'];
        $svgRelative = $relativeDir.'/'.basename($svgAbsolute);
        $pdfAbsolute = $result['pdf_path'] ?? null;
        $pdfRelative = $pdfAbsolute ? $relativeDir.'/'.basename($pdfAbsolute) : null;

        $job->update([
            'status' => GenerationJobStatus::Succeeded,
            'result_payload' => $result,
            'output_svg_path' => $svgRelative,
            'output_pdf_path' => $pdfRelative,
            'finished_at' => now(),
        ]);

        // Krytyka stylu (lokalna AI) — nie blokuje sukcesu generacji.
        $critique = $critic->critique($result, $params);
        if ($critique !== null) {
            $result['ai_critique'] = $critique;
            $job->update(['result_payload' => $result]);
        }

        ProjectAsset::query()->create([
            'cardboard_project_id' => $project->id,
            'type' => AssetType::OutputSvg,
            'disk' => config('geometry.output_disk'),
            'path' => $svgRelative,
            'original_name' => basename($svgAbsolute),
            'mime_type' => 'image/svg+xml',
            'size_bytes' => file_exists($svgAbsolute) ? filesize($svgAbsolute) : null,
            'meta' => [
                'generation_job_id' => $job->id,
                'parts' => $result['parts'] ?? [],
                'page_count' => $result['page_count'] ?? 1,
                'multisheet' => $result['multisheet'] ?? false,
            ],
        ]);

        foreach ($result['svg_paths'] ?? [] as $extraSvg) {
            $extraBasename = basename($extraSvg);
            if ($extraBasename === basename($svgAbsolute)) {
                continue;
            }
            $extraRelative = $relativeDir.'/'.$extraBasename;
            ProjectAsset::query()->create([
                'cardboard_project_id' => $project->id,
                'type' => AssetType::OutputSvg,
                'disk' => config('geometry.output_disk'),
                'path' => $extraRelative,
                'original_name' => $extraBasename,
                'mime_type' => 'image/svg+xml',
                'size_bytes' => file_exists($extraSvg) ? filesize($extraSvg) : null,
                'meta' => [
                    'generation_job_id' => $job->id,
                    'page' => true,
                ],
            ]);
        }

        if ($pdfAbsolute && file_exists($pdfAbsolute)) {
            ProjectAsset::query()->create([
                'cardboard_project_id' => $project->id,
                'type' => AssetType::OutputPdf,
                'disk' => config('geometry.output_disk'),
                'path' => $pdfRelative,
                'original_name' => basename($pdfAbsolute),
                'mime_type' => 'application/pdf',
                'size_bytes' => filesize($pdfAbsolute),
                'meta' => [
                    'generation_job_id' => $job->id,
                    'page_count' => $result['page_count'] ?? 1,
                ],
            ]);
        }

        foreach ([
            ['key' => 'instruction_svg_path', 'type' => AssetType::Instructions],
            ['key' => 'formers_svg_path', 'type' => AssetType::Formers],
        ] as $layer) {
            $abs = $result[$layer['key']] ?? null;
            if (! $abs || ! file_exists($abs)) {
                continue;
            }
            $rel = $relativeDir.'/'.basename($abs);
            ProjectAsset::query()->create([
                'cardboard_project_id' => $project->id,
                'type' => $layer['type'],
                'disk' => config('geometry.output_disk'),
                'path' => $rel,
                'original_name' => basename($abs),
                'mime_type' => 'image/svg+xml',
                'size_bytes' => filesize($abs),
                'meta' => [
                    'generation_job_id' => $job->id,
                    'layer' => $layer['type']->value,
                ],
            ]);
        }

        $project->update([
            'status' => ProjectStatus::Completed,
            'latest_svg_path' => $svgRelative,
            'latest_pdf_path' => $pdfRelative,
            'parameters' => $job->request_payload,
        ]);
    }

    public function failed(?Throwable $exception): void
    {
        $job = $this->generationJob->fresh();

        if (! $job) {
            return;
        }

        $job->update([
            'status' => GenerationJobStatus::Failed,
            'error_message' => $exception?->getMessage(),
            'finished_at' => now(),
        ]);

        $job->project?->update([
            'status' => ProjectStatus::Failed,
        ]);
    }
}
