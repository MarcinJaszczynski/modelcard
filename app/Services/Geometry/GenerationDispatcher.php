<?php

namespace App\Services\Geometry;

use App\Enums\GenerationJobStatus;
use App\Enums\PrimitiveShape;
use App\Enums\ProjectStatus;
use App\Jobs\ProcessGenerationJob;
use App\Models\CardboardProject;
use App\Models\GenerationJob;

class GenerationDispatcher
{
    public function dispatch(CardboardProject $project, ?array $parameters = null): GenerationJob
    {
        $params = $parameters ?? $project->resolvedParameters();

        $job = GenerationJob::query()->create([
            'cardboard_project_id' => $project->id,
            'status' => GenerationJobStatus::Queued,
            'shape' => $project->shape ?? PrimitiveShape::Box,
            'request_payload' => $params,
        ]);

        $project->update([
            'status' => ProjectStatus::Generating,
            'parameters' => $params,
        ]);

        ProcessGenerationJob::dispatch($job);

        return $job;
    }

    public function dispatchSync(CardboardProject $project, ?array $parameters = null): GenerationJob
    {
        $params = $parameters ?? $project->resolvedParameters();

        $job = GenerationJob::query()->create([
            'cardboard_project_id' => $project->id,
            'status' => GenerationJobStatus::Queued,
            'shape' => $project->shape ?? PrimitiveShape::Box,
            'request_payload' => $params,
        ]);

        $project->update([
            'status' => ProjectStatus::Generating,
            'parameters' => $params,
        ]);

        ProcessGenerationJob::dispatchSync($job);

        return $job->fresh();
    }
}
