<?php

namespace App\Models;

use App\Enums\GenerationJobStatus;
use App\Enums\PrimitiveShape;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Str;

class GenerationJob extends Model
{
    protected $fillable = [
        'uuid',
        'cardboard_project_id',
        'status',
        'shape',
        'request_payload',
        'result_payload',
        'output_svg_path',
        'output_pdf_path',
        'error_message',
        'started_at',
        'finished_at',
    ];

    protected function casts(): array
    {
        return [
            'status' => GenerationJobStatus::class,
            'shape' => PrimitiveShape::class,
            'request_payload' => 'array',
            'result_payload' => 'array',
            'started_at' => 'datetime',
            'finished_at' => 'datetime',
        ];
    }

    protected static function booted(): void
    {
        static::creating(function (GenerationJob $job): void {
            if (empty($job->uuid)) {
                $job->uuid = (string) Str::uuid();
            }
        });
    }

    public function project(): BelongsTo
    {
        return $this->belongsTo(CardboardProject::class, 'cardboard_project_id');
    }
}
