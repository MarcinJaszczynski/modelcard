<?php

use App\Http\Controllers\ProjectPdfDownloadController;
use App\Http\Controllers\ProjectSvgDownloadController;
use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return redirect('/admin');
});

Route::middleware(['web', 'auth'])->group(function () {
    Route::get('/projects/{project}/svg', ProjectSvgDownloadController::class)
        ->name('projects.svg.download');
    Route::get('/projects/{project}/pdf', ProjectPdfDownloadController::class)
        ->name('projects.pdf.download');
});
