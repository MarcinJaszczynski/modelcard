<?php

namespace App\Filament\Resources\CardboardProjects\Pages;

use App\Enums\AssetType;
use App\Enums\GenerationJobStatus;
use App\Enums\PrimitiveShape;
use App\Filament\Resources\CardboardProjects\CardboardProjectResource;
use App\Models\CardboardProject;
use App\Models\ProjectAsset;
use App\Services\Geometry\GenerationDispatcher;
use Filament\Actions\Action;
use Filament\Actions\DeleteAction;
use Filament\Actions\ViewAction;
use Filament\Notifications\Notification;
use Filament\Resources\Pages\EditRecord;
use Illuminate\Support\Facades\Storage;

class EditCardboardProject extends EditRecord
{
    protected static string $resource = CardboardProjectResource::class;

    /** @var list<string> */
    protected array $pendingUploads = [];

    protected function getHeaderActions(): array
    {
        return [
            Action::make('generate')
                ->label('Generuj planszę')
                ->icon('heroicon-o-cog-6-tooth')
                ->color('primary')
                ->requiresConfirmation()
                ->action(function (GenerationDispatcher $dispatcher): void {
                    $this->save(shouldRedirect: false);

                    $job = $dispatcher->dispatchSync($this->record->fresh());

                    if ($job->status === GenerationJobStatus::Succeeded) {
                        Notification::make()
                            ->title('Plansza wygenerowana (SVG + PDF)')
                            ->success()
                            ->send();
                    } else {
                        Notification::make()
                            ->title('Generowanie nie powiodło się')
                            ->body($job->error_message ?? 'Nieznany błąd')
                            ->danger()
                            ->send();
                    }

                    $this->record->refresh();
                }),
            ViewAction::make(),
            DeleteAction::make(),
        ];
    }

    protected function mutateFormDataBeforeSave(array $data): array
    {
        $this->pendingUploads = array_values(array_filter(
            $data['reference_uploads'] ?? [],
            fn ($path) => is_string($path) && $path !== ''
        ));

        unset($data['reference_uploads']);

        $shape = PrimitiveShape::tryFrom($data['shape'] ?? '') ?? $this->record->shape ?? PrimitiveShape::Box;
        $defaults = match ($shape) {
            PrimitiveShape::Cylinder => CardboardProject::defaultCylinderParameters(),
            PrimitiveShape::Building => CardboardProject::defaultBuildingParameters(),
            PrimitiveShape::Wagon => CardboardProject::defaultWagonParameters(),
            default => CardboardProject::defaultBoxParameters(),
        };

        $data['parameters'] = array_merge($defaults, $data['parameters'] ?? []);

        return $data;
    }

    protected function afterSave(): void
    {
        $disk = Storage::disk('local');

        foreach ($this->pendingUploads as $path) {
            $exists = ProjectAsset::query()
                ->where('cardboard_project_id', $this->record->id)
                ->where('path', $path)
                ->exists();

            if ($exists) {
                continue;
            }

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
}
