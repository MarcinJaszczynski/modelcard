<?php

namespace App\Http\Controllers;

use App\Models\CardboardProject;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Storage;
use Symfony\Component\HttpFoundation\StreamedResponse;

class ProjectPdfDownloadController extends Controller
{
    public function __invoke(Request $request, CardboardProject $project): StreamedResponse
    {
        abort_unless($project->latest_pdf_path, 404, 'Brak wygenerowanego PDF.');

        $disk = Storage::disk(config('geometry.output_disk'));

        abort_unless($disk->exists($project->latest_pdf_path), 404);

        return $disk->download(
            $project->latest_pdf_path,
            str($project->name)->slug().'.pdf',
            ['Content-Type' => 'application/pdf']
        );
    }
}
