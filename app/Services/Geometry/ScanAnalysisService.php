<?php

namespace App\Services\Geometry;

use App\Enums\AssetType;
use App\Enums\PartRole;
use App\Models\ProjectAsset;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

class ScanAnalysisService
{
    public function __construct(private GeometryWorkerClient $client) {}

    /**
     * Analizuje raster assetu i zapisuje overlay + JSON sugestii jako nowe assety.
     *
     * @return array{overlay: ProjectAsset, suggestions: ProjectAsset, result: array}
     */
    public function analyze(ProjectAsset $asset): array
    {
        $absolute = $asset->absolutePath();

        if (! is_file($absolute)) {
            throw new \RuntimeException('Plik assetu nie istnieje na dysku.');
        }

        $uuid = (string) Str::uuid();
        $relativeDir = 'analyses/'.$uuid;
        $absoluteDir = Storage::disk(config('geometry.output_disk'))->path($relativeDir);

        $result = $this->client->analyze([
            'image_path' => $absolute,
            'output_dir' => $absoluteDir,
            'max_lines' => 80,
        ]);

        $overlayAbs = $result['overlay_path'];
        $suggestionsAbs = $result['suggestions_path'];
        $overlayRel = $relativeDir.'/'.basename($overlayAbs);
        $suggestionsRel = $relativeDir.'/'.basename($suggestionsAbs);

        $overlayAsset = ProjectAsset::query()->create([
            'cardboard_project_id' => $asset->cardboard_project_id,
            'type' => AssetType::AnalysisOverlay,
            'part_role' => PartRole::CutLine,
            'tags' => ['cv', 'suggestions', 'overlay'],
            'annotation' => sprintf(
                'Sugestie CV: %d linii (cut=%d, fold=%d). Wymaga weryfikacji.',
                $result['line_count'] ?? 0,
                $result['cut_count'] ?? 0,
                $result['fold_count'] ?? 0,
            ),
            'disk' => config('geometry.output_disk'),
            'path' => $overlayRel,
            'original_name' => basename($overlayAbs),
            'mime_type' => 'image/png',
            'size_bytes' => file_exists($overlayAbs) ? filesize($overlayAbs) : null,
            'meta' => [
                'source_asset_id' => $asset->id,
                'line_count' => $result['line_count'] ?? 0,
                'cut_count' => $result['cut_count'] ?? 0,
                'fold_count' => $result['fold_count'] ?? 0,
                'note' => $result['note'] ?? null,
            ],
        ]);

        $suggestionsAsset = ProjectAsset::query()->create([
            'cardboard_project_id' => $asset->cardboard_project_id,
            'type' => AssetType::AnalysisJson,
            'part_role' => PartRole::Unknown,
            'tags' => ['cv', 'suggestions', 'json'],
            'annotation' => 'JSON sugestii linii (cut/fold) z analizy skanu.',
            'disk' => config('geometry.output_disk'),
            'path' => $suggestionsRel,
            'original_name' => basename($suggestionsAbs),
            'mime_type' => 'application/json',
            'size_bytes' => file_exists($suggestionsAbs) ? filesize($suggestionsAbs) : null,
            'meta' => [
                'source_asset_id' => $asset->id,
                'overlay_asset_id' => $overlayAsset->id,
            ],
        ]);

        $meta = $asset->meta ?? [];
        $meta['last_analysis'] = [
            'overlay_asset_id' => $overlayAsset->id,
            'suggestions_asset_id' => $suggestionsAsset->id,
            'line_count' => $result['line_count'] ?? 0,
            'analyzed_at' => now()->toIso8601String(),
        ];
        $asset->update(['meta' => $meta]);

        return [
            'overlay' => $overlayAsset,
            'suggestions' => $suggestionsAsset,
            'result' => $result,
        ];
    }
}
