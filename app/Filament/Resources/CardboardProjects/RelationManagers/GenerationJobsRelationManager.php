<?php

namespace App\Filament\Resources\CardboardProjects\RelationManagers;

use App\Enums\GenerationJobStatus;
use Filament\Resources\RelationManagers\RelationManager;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Table;

class GenerationJobsRelationManager extends RelationManager
{
    protected static string $relationship = 'generationJobs';

    protected static ?string $title = 'Joby generacji';

    public function table(Table $table): Table
    {
        return $table
            ->defaultSort('id', 'desc')
            ->columns([
                TextColumn::make('uuid')
                    ->label('UUID')
                    ->copyable()
                    ->limit(13),
                TextColumn::make('status')
                    ->label('Status')
                    ->badge()
                    ->formatStateUsing(fn ($state) => $state instanceof GenerationJobStatus ? $state->label() : (string) $state),
                TextColumn::make('shape')
                    ->label('Bryła')
                    ->formatStateUsing(fn ($state) => $state?->label() ?? (string) $state),
                TextColumn::make('output_svg_path')
                    ->label('SVG')
                    ->limit(40),
                TextColumn::make('error_message')
                    ->label('Błąd')
                    ->limit(40)
                    ->toggleable(isToggledHiddenByDefault: true),
                TextColumn::make('finished_at')
                    ->label('Zakończono')
                    ->dateTime('Y-m-d H:i')
                    ->placeholder('—'),
            ])
            ->headerActions([])
            ->recordActions([])
            ->toolbarActions([]);
    }
}
