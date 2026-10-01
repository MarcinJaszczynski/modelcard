<?php

namespace App\Services\Geometry;

use RuntimeException;
use Symfony\Component\Process\Process;

/**
 * Klient workera geometrii / analizy skanów.
 */
class GeometryWorkerClient
{
    public function generate(array $payload): array
    {
        return match (config('geometry.driver')) {
            'http' => $this->viaHttp('/v1/generate', $payload),
            default => $this->viaCli('generate', $payload),
        };
    }

    public function analyze(array $payload): array
    {
        return match (config('geometry.driver')) {
            'http' => $this->viaHttp('/v1/analyze', $payload),
            default => $this->viaCli('analyze', $payload),
        };
    }

    private function viaCli(string $command, array $payload): array
    {
        $modulePath = config('geometry.cli.module_path');
        $python = config('geometry.cli.python');
        $outputDir = $payload['output_dir'] ?? storage_path('app/private/tmp');
        $inputFile = rtrim($outputDir, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR."request_{$command}.json";

        if (! is_dir($outputDir)) {
            mkdir($outputDir, 0755, true);
        }

        file_put_contents($inputFile, json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

        $process = new Process([
            $python,
            '-m',
            'geometry_worker',
            $command,
            '--input',
            $inputFile,
        ], $modulePath);

        $process->setTimeout(180);
        $process->run();

        if (! $process->isSuccessful()) {
            throw new RuntimeException(
                "Geometry worker CLI ({$command}) failed: ".$process->getErrorOutput().$process->getOutput()
            );
        }

        $decoded = json_decode($process->getOutput(), true);

        if (! is_array($decoded) || ($decoded['ok'] ?? false) !== true) {
            throw new RuntimeException(
                "Invalid geometry worker response ({$command}): ".$process->getOutput()
            );
        }

        return $decoded;
    }

    private function viaHttp(string $path, array $payload): array
    {
        $base = rtrim(config('geometry.http.base_url'), '/');
        $timeout = config('geometry.http.timeout');

        $response = \Illuminate\Support\Facades\Http::timeout($timeout)
            ->post($base.$path, $payload);

        if (! $response->successful()) {
            throw new RuntimeException(
                'Geometry worker HTTP failed: '.$response->body()
            );
        }

        $decoded = $response->json();

        if (! is_array($decoded) || ($decoded['ok'] ?? false) !== true) {
            throw new RuntimeException('Invalid geometry worker HTTP response');
        }

        return $decoded;
    }
}
