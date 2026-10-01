<?php

namespace App\Filament\Resources\CardboardProjects\Pages;

use App\Enums\GenerationJobStatus;
use App\Filament\Resources\CardboardProjects\CardboardProjectResource;
use App\Services\Geometry\GenerationDispatcher;
use Filament\Actions\Action;
use Filament\Actions\EditAction;
use Filament\Notifications\Notification;
use Filament\Resources\Pages\ViewRecord;
use Illuminate\Support\Facades\Storage;

class ViewCardboardProject extends ViewRecord
{
    protected static string $resource = CardboardProjectResource::class;

    protected function getHeaderActions(): array
    {
        return [
            Action::make('generate')
                ->label('Generuj planszę')
                ->icon('heroicon-o-cog-6-tooth')
                ->color('primary')
                ->requiresConfirmation()
                ->modalHeading('Generować rozwinięcie?')
                ->modalDescription('Worker: bryła → unfolding → SVG + PDF.')
                ->action(function (GenerationDispatcher $dispatcher): void {
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
            Action::make('downloadSvg')
                ->label('SVG')
                ->icon('heroicon-o-arrow-down-tray')
                ->url(fn () => $this->record->latest_svg_path
                    ? route('projects.svg.download', $this->record)
                    : null)
                ->visible(fn () => filled($this->record->latest_svg_path)
                    && Storage::disk(config('geometry.output_disk'))->exists($this->record->latest_svg_path)),
            Action::make('downloadPdf')
                ->label('PDF')
                ->icon('heroicon-o-document-arrow-down')
                ->url(fn () => $this->record->latest_pdf_path
                    ? route('projects.pdf.download', $this->record)
                    : null)
                ->visible(fn () => filled($this->record->latest_pdf_path)
                    && Storage::disk(config('geometry.output_disk'))->exists($this->record->latest_pdf_path)),
            EditAction::make(),
        ];
    }
}
