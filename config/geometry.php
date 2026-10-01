<?php

return [
    /*
    |--------------------------------------------------------------------------
    | Geometry worker
    |--------------------------------------------------------------------------
    |
    | Laravel wysyła joby do lokalnego workera Python (CLI lub HTTP FastAPI).
    | Domyślnie CLI z venv workera — stabilniejsze lokalnie bez Redis/HTTP.
    |
    */
    'driver' => env('GEOMETRY_WORKER_DRIVER', 'cli'),

    'cli' => [
        'python' => env(
            'GEOMETRY_WORKER_PYTHON',
            base_path('services/geometry-worker/.venv/bin/python')
        ),
        'module_path' => env(
            'GEOMETRY_WORKER_PATH',
            base_path('services/geometry-worker')
        ),
    ],

    'http' => [
        'base_url' => env('GEOMETRY_WORKER_URL', 'http://127.0.0.1:8090'),
        'timeout' => (int) env('GEOMETRY_WORKER_TIMEOUT', 60),
    ],

    'output_disk' => env('GEOMETRY_OUTPUT_DISK', 'local'),
    'output_directory' => 'generations',
];
