<?php

namespace App\Filament\Resources\CardboardProjects\Pages;

use App\Enums\AssetType;
use App\Enums\PrimitiveShape;
use App\Enums\ProjectStatus;
use App\Filament\Resources\CardboardProjects\CardboardProjectResource;
use App\Models\CardboardProject;
use App\Models\ProjectAsset;
use Filament\Resources\Pages\CreateRecord;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Storage;

class CreateCardboardProject extends CreateRecord
{
    protected static string $resource = CardboardProjectResource::class;

    /** @var list<string> */
    protected array $pendingUploads = [];

    protected function mutateFormDataBeforeCreate(array $data): array
    {
        $this->pendingUploads = array_values(array_filter(
            $data['reference_uploads'] ?? [],
            fn ($path) => is_string($path) && $path !== ''
        ));

        unset($data['reference_uploads']);

        $data['user_id'] = Auth::id();
        $data['status'] = $data['status'] ?? ProjectStatus::Draft->value;
        $shape = PrimitiveShape::tryFrom($data['shape'] ?? '') ?? PrimitiveShape::Box;
        $data['shape'] = $shape->value;

        $defaults = match ($shape) {
            PrimitiveShape::Cylinder => CardboardProject::defaultCylinderParameters(),
            PrimitiveShape::Building => CardboardProject::defaultBuildingParameters(),
            PrimitiveShape::Wagon => CardboardProject::defaultWagonParameters(),
            default => CardboardProject::defaultBoxParameters(),
        };

        $data['parameters'] = array_merge($defaults, $data['parameters'] ?? []);

        return $data;
    }

    protected function afterCreate(): void
    {
        $disk = Storage::disk('local');

        foreach ($this->pendingUploads as $path) {
            ProjectAsset::query()->create([
                'cardboard_project_id' => $this->record->id,
                'type' => AssetType::Reference,
                'disk' => 'local',
                'path' => $path,
                'original_name' => basename($path),
                'mime_type' => $disk->exists($path) ? $disk->mimeType($path) : null,
                'size_bytes' => $disk->exists($path) ? $disk->size($path) : null,
            ]);
        }
    }

    protected function getRedirectUrl(): string
    {
        return $this->getResource()::getUrl('view', ['record' => $this->record]);
    }
}
