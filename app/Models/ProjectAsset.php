<?php

namespace App\Models;

use App\Enums\AssetType;
use App\Enums\PartRole;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Facades\Storage;

class ProjectAsset extends Model
{
    protected $fillable = [
        'cardboard_project_id',
        'type',
        'part_role',
        'tags',
        'annotation',
        'disk',
        'path',
        'original_name',
        'mime_type',
        'size_bytes',
        'meta',
    ];

    protected function casts(): array
    {
        return [
            'type' => AssetType::class,
            'part_role' => PartRole::class,
            'tags' => 'array',
            'meta' => 'array',
        ];
    }

    public function project(): BelongsTo
    {
        return $this->belongsTo(CardboardProject::class, 'cardboard_project_id');
    }

    public function absolutePath(): string
    {
        return Storage::disk($this->disk)->path($this->path);
    }
}
