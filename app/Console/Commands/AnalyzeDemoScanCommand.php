<?php

namespace App\Console\Commands;

use App\Enums\AssetType;
use App\Models\CardboardProject;
use App\Models\ProjectAsset;
use App\Services\Geometry\ScanAnalysisService;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Storage;

class AnalyzeDemoScanCommand extends Command
{
    protected $signature = 'modelarz:demo-analyze
        {--project= : ID projektu (domyślnie ostatni)}
        {--asset= : ID assetu do analizy}';

    protected $description = 'Demo Fazy 3: analiza skanu (linie cut/fold) → overlay';

    public function handle(ScanAnalysisService $service): int
    {
        $asset = null;

        if ($this->option('asset')) {
            $asset = ProjectAsset::query()->find($this->option('asset'));
        } else {
            $projectId = $this->option('project') ?: CardboardProject::query()->latest('id')->value('id');
            $project = CardboardProject::query()->find($projectId);

            if (! $project) {
                $this->error('Brak projektu — utwórz projekt lub podaj --project=');

                return self::FAILURE;
            }

            // Jeśli nie ma skanu — wygeneruj syntetyczny obraz z linii (test bez prawdziwego skanu)
            $asset = $project->assets()
                ->whereIn('type', ['scan', 'photo', 'drawing', 'reference'])
                ->latest('id')
                ->first();

            if (! $asset) {
                $relative = 'references/demo_scan_synthetic.png';
                $abs = Storage::disk('local')->path($relative);
                @mkdir(dirname($abs), 0755, true);
                $this->makeSyntheticScan($abs);

                $asset = ProjectAsset::query()->create([
                    'cardboard_project_id' => $project->id,
                    'type' => AssetType::Scan,
                    'disk' => 'local',
                    'path' => $relative,
                    'original_name' => 'demo_scan_synthetic.png',
                    'mime_type' => 'image/png',
                    'size_bytes' => filesize($abs),
                    'annotation' => 'Syntetyczny skan demo do testu CV',
                ]);
                $this->line('Utworzono syntetyczny skan: '.$relative);
            }
        }

        if (! $asset) {
            $this->error('Nie znaleziono assetu');

            return self::FAILURE;
        }

        $out = $service->analyze($asset);

        $this->info('OK — analiza assetu #'.$asset->id);
        $this->line('Linie: '.$out['result']['line_count']);
        $this->line('Cut: '.$out['result']['cut_count'].' · Fold: '.$out['result']['fold_count']);
        $this->line('Overlay asset #'.$out['overlay']->id.' → '.$out['overlay']->path);
        $this->line('JSON asset #'.$out['suggestions']->id.' → '.$out['suggestions']->path);

        return self::SUCCESS;
    }

    private function makeSyntheticScan(string $path): void
    {
        // Prosty PNG bez zależności: użyj workera Python + OpenCV jeśli dostępny,
        // inaczej minimalny PPM→ przez GD jeśli jest.
        if (function_exists('imagecreatetruecolor')) {
            $im = imagecreatetruecolor(800, 600);
            $white = imagecolorallocate($im, 250, 248, 240);
            $black = imagecolorallocate($im, 20, 20, 20);
            $gray = imagecolorallocate($im, 90, 90, 90);
            imagefilledrectangle($im, 0, 0, 800, 600, $white);
            // cut lines
            imageline($im, 80, 80, 720, 80, $black);
            imageline($im, 80, 80, 80, 520, $black);
            imageline($im, 720, 80, 720, 520, $black);
            imageline($im, 80, 520, 720, 520, $black);
            imageline($im, 80, 300, 720, 300, $black);
            // fold-like dashed
            for ($x = 80; $x < 720; $x += 16) {
                imageline($im, $x, 200, min($x + 8, 720), 200, $gray);
            }
            imagepng($im, $path);
            imagedestroy($im);

            return;
        }

        throw new \RuntimeException('Brak GD — nie można wygenerować syntetycznego skanu.');
    }
}
