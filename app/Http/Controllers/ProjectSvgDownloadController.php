<?php

namespace App\Http\Controllers;

use App\Models\CardboardProject;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Storage;
use Symfony\Component\HttpFoundation\StreamedResponse;

class ProjectSvgDownloadController extends Controller
{
    public function __invoke(Request $request, CardboardProject $project): StreamedResponse
    {
        abort_unless($project->latest_svg_path, 404, 'Brak wygenerowanego SVG.');

        $disk = Storage::disk(config('geometry.output_disk'));

        abort_unless($disk->exists($project->latest_svg_path), 404);

        return $disk->download(
            $project->latest_svg_path,
            str($project->name)->slug().'.svg',
            ['Content-Type' => 'image/svg+xml']
        );
    }
}
