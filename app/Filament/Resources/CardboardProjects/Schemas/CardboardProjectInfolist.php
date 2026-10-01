<?php

namespace App\Filament\Resources\CardboardProjects\Schemas;

use Filament\Infolists\Components\TextEntry;
use Filament\Schemas\Components\Section;
use Filament\Schemas\Schema;
use Illuminate\Support\Facades\Storage;

class CardboardProjectInfolist
{
    public static function configure(Schema $schema): Schema
    {
        return $schema
            ->components([
                Section::make('Podsumowanie')
                    ->columns(2)
                    ->schema([
                        TextEntry::make('name')->label('Nazwa'),
                        TextEntry::make('status')
                            ->label('Status')
                            ->formatStateUsing(fn ($state) => $state?->label() ?? (string) $state)
                            ->badge(),
                        TextEntry::make('shape')
                            ->label('Bryła')
                            ->formatStateUsing(fn ($state) => $state?->label() ?? (string) $state),
                        TextEntry::make('scale')->label('Skala')->placeholder('—'),
                        TextEntry::make('model_type')->label('Typ modelu')->placeholder('—'),
                        TextEntry::make('publisher')->label('Wydawca / źródło')->placeholder('—'),
                        TextEntry::make('year')->label('Rok')->placeholder('—'),
                        TextEntry::make('description')
                            ->label('Opis')
                            ->columnSpanFull()
                            ->placeholder('—'),
                    ]),
                Section::make('Parametry')
                    ->columns(3)
                    ->schema([
                        TextEntry::make('parameters.width_mm')->label('Szerokość [mm]')->placeholder('—'),
                        TextEntry::make('parameters.depth_mm')->label('Głębokość [mm]')->placeholder('—'),
                        TextEntry::make('parameters.length_mm')->label('Długość [mm]')->placeholder('—'),
                        TextEntry::make('parameters.wagon_width_mm')->label('Szer. wagonu [mm]')->placeholder('—'),
                        TextEntry::make('parameters.diameter_mm')->label('Średnica [mm]')->placeholder('—'),
                        TextEntry::make('parameters.height_mm')->label('Wysokość [mm]')->placeholder('—'),
                        TextEntry::make('parameters.wall_height_mm')->label('Ściana [mm]')->placeholder('—'),
                        TextEntry::make('parameters.roof_rise_mm')->label('Wznios dachu [mm]')->placeholder('—'),
                        TextEntry::make('parameters.chassis_height_mm')->label('Podwozie [mm]')->placeholder('—'),
                        TextEntry::make('parameters.wheel_diameter_mm')->label('Koło Ø [mm]')->placeholder('—'),
                        TextEntry::make('parameters.flap_mm')->label('Zakładka [mm]'),
                        TextEntry::make('parameters.segments')->label('Segmenty')->placeholder('—'),
                        TextEntry::make('parameters.style')->label('Styl'),
                        TextEntry::make('parameters.sheet')->label('Arkusz'),
                    ]),
                Section::make('Wyniki generacji')
                    ->schema([
                        TextEntry::make('latest_svg_path')
                            ->label('SVG')
                            ->formatStateUsing(fn ($state) => $state ?: 'Brak')
                            ->url(fn ($record) => $record->latest_svg_path
                                ? route('projects.svg.download', $record)
                                : null),
                        TextEntry::make('latest_pdf_path')
                            ->label('PDF')
                            ->formatStateUsing(fn ($state) => $state ?: 'Brak')
                            ->url(fn ($record) => $record->latest_pdf_path
                                ? route('projects.pdf.download', $record)
                                : null),
                        TextEntry::make('svg_preview')
                            ->label('Podgląd SVG')
                            ->html()
                            ->state(function ($record): string {
                                if (! $record->latest_svg_path) {
                                    return '<p class="text-sm text-gray-500">Wygeneruj planszę, aby zobaczyć podgląd.</p>';
                                }

                                $disk = Storage::disk(config('geometry.output_disk'));
                                if (! $disk->exists($record->latest_svg_path)) {
                                    return '<p class="text-sm text-red-500">Plik SVG nie istnieje na dysku.</p>';
                                }

                                $svg = $disk->get($record->latest_svg_path);

                                return '<div style="border:1px solid #ddd;background:#fff;padding:8px;overflow:auto;max-height:70vh">'.$svg.'</div>';
                            })
                            ->columnSpanFull(),
                    ]),
            ]);
    }
}
