<?php

namespace App\Filament\Resources\CardboardProjects\Tables;

use App\Enums\ProjectStatus;
use Filament\Actions\Action;
use Filament\Actions\BulkActionGroup;
use Filament\Actions\DeleteBulkAction;
use Filament\Actions\EditAction;
use Filament\Actions\ViewAction;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Table;
use Illuminate\Support\Facades\Storage;

class CardboardProjectsTable
{
    public static function configure(Table $table): Table
    {
        return $table
            ->columns([
                TextColumn::make('name')
                    ->label('Nazwa')
                    ->searchable()
                    ->sortable(),
                TextColumn::make('shape')
                    ->label('Bryła')
                    ->badge()
                    ->formatStateUsing(fn ($state) => $state?->label() ?? (string) $state),
                TextColumn::make('model_type')
                    ->label('Typ')
                    ->placeholder('—')
                    ->toggleable(),
                TextColumn::make('status')
                    ->label('Status')
                    ->badge()
                    ->color(fn (ProjectStatus|string|null $state): string => match ($state instanceof ProjectStatus ? $state : ProjectStatus::tryFrom((string) $state)) {
                        ProjectStatus::Completed => 'success',
                        ProjectStatus::Generating => 'warning',
                        ProjectStatus::Failed => 'danger',
                        default => 'gray',
                    })
                    ->formatStateUsing(fn ($state) => $state instanceof ProjectStatus ? $state->label() : (string) $state),
                TextColumn::make('updated_at')
                    ->label('Aktualizacja')
                    ->dateTime('Y-m-d H:i')
                    ->sortable(),
            ])
            ->defaultSort('updated_at', 'desc')
            ->filters([])
            ->recordActions([
                ViewAction::make(),
                EditAction::make(),
                Action::make('downloadSvg')
                    ->label('SVG')
                    ->icon('heroicon-o-arrow-down-tray')
                    ->url(fn ($record) => $record->latest_svg_path
                        ? route('projects.svg.download', $record)
                        : null)
                    ->visible(fn ($record) => filled($record->latest_svg_path)
                        && Storage::disk(config('geometry.output_disk'))->exists($record->latest_svg_path)),
                Action::make('downloadPdf')
                    ->label('PDF')
                    ->icon('heroicon-o-document-arrow-down')
                    ->url(fn ($record) => $record->latest_pdf_path
                        ? route('projects.pdf.download', $record)
                        : null)
                    ->visible(fn ($record) => filled($record->latest_pdf_path)
                        && Storage::disk(config('geometry.output_disk'))->exists($record->latest_pdf_path)),
            ])
            ->toolbarActions([
                BulkActionGroup::make([
                    DeleteBulkAction::make(),
                ]),
            ]);
    }
}
