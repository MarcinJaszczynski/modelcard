<?php

namespace App\Filament\Resources\CardboardProjects\Schemas;

use App\Enums\PrimitiveShape;
use App\Enums\ProjectStatus;
use App\Enums\SheetStyle;
use Filament\Forms\Components\FileUpload;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\Textarea;
use Filament\Forms\Components\TextInput;
use Filament\Forms\Components\Toggle;
use Filament\Schemas\Components\Section;
use Filament\Schemas\Components\Utilities\Get;
use Filament\Schemas\Schema;

class CardboardProjectForm
{
    public static function configure(Schema $schema): Schema
    {
        return $schema
            ->components([
                Section::make('Projekt')
                    ->columns(2)
                    ->schema([
                        TextInput::make('name')
                            ->label('Nazwa')
                            ->required()
                            ->maxLength(255)
                            ->columnSpanFull(),
                        Textarea::make('description')
                            ->label('Opis')
                            ->rows(3)
                            ->columnSpanFull(),
                        Select::make('status')
                            ->label('Status')
                            ->options(collect(ProjectStatus::cases())->mapWithKeys(
                                fn (ProjectStatus $s) => [$s->value => $s->label()]
                            ))
                            ->default(ProjectStatus::Draft->value)
                            ->required(),
                        Select::make('shape')
                            ->label('Bryła')
                            ->options(collect(PrimitiveShape::cases())->mapWithKeys(
                                fn (PrimitiveShape $s) => [$s->value => $s->label()]
                            ))
                            ->default(PrimitiveShape::Box->value)
                            ->live()
                            ->required(),
                        TextInput::make('scale')
                            ->label('Skala (tekst)')
                            ->placeholder('1:25')
                            ->maxLength(32)
                            ->helperText('Możesz też wybrać preset poniżej w parametrach.'),
                        Select::make('parameters.scale')
                            ->label('Skala (preset Answer-like)')
                            ->options(collect(config('modelarz.scales'))->mapWithKeys(
                                fn (array $meta, string $key) => [$key => $meta['label']]
                            ))
                            ->default(config('modelarz.default_scale'))
                            ->required(),
                        Select::make('parameters.series')
                            ->label('Seria / poziom')
                            ->options(collect(config('modelarz.series'))->mapWithKeys(
                                fn (array $meta, string $key) => [$key => $meta['label']]
                            ))
                            ->default(config('modelarz.default_series'))
                            ->live()
                            ->required(),
                        TextInput::make('model_type')
                            ->label('Typ modelu')
                            ->placeholder('np. budynek, wagon, samolot')
                            ->maxLength(64),
                        TextInput::make('publisher')
                            ->label('Wydawca / źródło')
                            ->maxLength(128),
                        TextInput::make('year')
                            ->label('Rok')
                            ->numeric()
                            ->minValue(1900)
                            ->maxValue(2100),
                    ]),
                Section::make('Parametry bryły (mm)')
                    ->columns(2)
                    ->schema([
                        TextInput::make('parameters.width_mm')
                            ->label('Szerokość')
                            ->numeric()
                            ->default(80)
                            ->minValue(5)
                            ->suffix('mm')
                            ->visible(fn (Get $get): bool => in_array($get('shape'), [
                                PrimitiveShape::Box->value,
                                PrimitiveShape::Building->value,
                                null,
                                '',
                            ], true)),
                        TextInput::make('parameters.depth_mm')
                            ->label('Głębokość')
                            ->numeric()
                            ->default(40)
                            ->minValue(5)
                            ->suffix('mm')
                            ->visible(fn (Get $get): bool => in_array($get('shape'), [
                                PrimitiveShape::Box->value,
                                PrimitiveShape::Building->value,
                                null,
                                '',
                            ], true)),
                        TextInput::make('parameters.length_mm')
                            ->label('Długość wagonu')
                            ->numeric()
                            ->default(100)
                            ->minValue(10)
                            ->suffix('mm')
                            ->visible(fn (Get $get): bool => $get('shape') === PrimitiveShape::Wagon->value),
                        TextInput::make('parameters.wagon_width_mm')
                            ->label('Szerokość wagonu')
                            ->numeric()
                            ->default(40)
                            ->minValue(10)
                            ->suffix('mm')
                            ->visible(fn (Get $get): bool => $get('shape') === PrimitiveShape::Wagon->value),
                        TextInput::make('parameters.diameter_mm')
                            ->label('Średnica')
                            ->numeric()
                            ->default(50)
                            ->minValue(5)
                            ->suffix('mm')
                            ->visible(fn (Get $get): bool => $get('shape') === PrimitiveShape::Cylinder->value),
                        TextInput::make('parameters.height_mm')
                            ->label('Wysokość')
                            ->numeric()
                            ->default(50)
                            ->minValue(5)
                            ->suffix('mm')
                            ->visible(fn (Get $get): bool => ! in_array($get('shape'), [
                                PrimitiveShape::Building->value,
                            ], true)),
                        TextInput::make('parameters.wall_height_mm')
                            ->label('Wysokość ściany')
                            ->numeric()
                            ->default(45)
                            ->minValue(5)
                            ->suffix('mm')
                            ->visible(fn (Get $get): bool => $get('shape') === PrimitiveShape::Building->value),
                        TextInput::make('parameters.roof_rise_mm')
                            ->label('Wznios dachu')
                            ->numeric()
                            ->default(25)
                            ->minValue(5)
                            ->suffix('mm')
                            ->visible(fn (Get $get): bool => $get('shape') === PrimitiveShape::Building->value),
                        TextInput::make('parameters.chassis_height_mm')
                            ->label('Wysokość podwozia')
                            ->numeric()
                            ->default(8)
                            ->minValue(2)
                            ->suffix('mm')
                            ->visible(fn (Get $get): bool => $get('shape') === PrimitiveShape::Wagon->value),
                        TextInput::make('parameters.wheel_diameter_mm')
                            ->label('Średnica koła')
                            ->numeric()
                            ->default(18)
                            ->minValue(5)
                            ->suffix('mm')
                            ->visible(fn (Get $get): bool => $get('shape') === PrimitiveShape::Wagon->value),
                        TextInput::make('parameters.flap_mm')
                            ->label('Zakładka sklejki')
                            ->numeric()
                            ->default(8)
                            ->required()
                            ->minValue(2)
                            ->suffix('mm'),
                        TextInput::make('parameters.segments')
                            ->label('Segmenty denka')
                            ->numeric()
                            ->default(24)
                            ->minValue(12)
                            ->maxValue(48)
                            ->visible(fn (Get $get): bool => $get('shape') === PrimitiveShape::Cylinder->value),
                        Select::make('parameters.style')
                            ->label('Styl / whethering')
                            ->options(collect(SheetStyle::cases())->mapWithKeys(
                                fn (SheetStyle $s) => [$s->value => $s->label()]
                            ))
                            ->default(SheetStyle::Clean->value)
                            ->required()
                            ->helperText('Warstwa graficzna na rozwinięciu (nie zmienia geometrii).'),
                        Toggle::make('parameters.markings')
                            ->label('Markings (okna / drzwi)')
                            ->default(true)
                            ->inline(false)
                            ->helperText('Dodaje okna/drzwi na building i wagon.'),
                        Toggle::make('parameters.instructions')
                            ->label('Arkusz instrukcji montażu')
                            ->default(true)
                            ->inline(false),
                        Toggle::make('parameters.formers')
                            ->label('Formierze / szkielet')
                            ->default(false)
                            ->inline(false)
                            ->helperText('Osobny arkusz do tektury grubszej (jak laserowy szkielet).'),
                        TextInput::make('parameters.former_thickness_mm')
                            ->label('Grubość formierzy')
                            ->numeric()
                            ->default(1.0)
                            ->suffix('mm')
                            ->visible(fn (Get $get): bool => (bool) $get('parameters.formers')),
                        Toggle::make('parameters.multisheet')
                            ->label('Wymuś wiele arkuszy')
                            ->default(false)
                            ->inline(false)
                            ->helperText('Packing paneli 1:1 zamiast skalowania całego netu.'),
                        Select::make('parameters.sheet')
                            ->label('Arkusz')
                            ->options([
                                'A4' => 'A4 (210×297 mm)',
                                'A3' => 'A3 (297×420 mm)',
                            ])
                            ->default('A4')
                            ->required(),
                    ]),
                Section::make('Materiały referencyjne')
                    ->description('Skany plansz, zdjęcia, rysunki — korpus stylu (Faza 0).')
                    ->schema([
                        FileUpload::make('reference_uploads')
                            ->label('Upload skanów / zdjęć / rysunków')
                            ->multiple()
                            ->disk('local')
                            ->directory('references')
                            ->visibility('private')
                            ->acceptedFileTypes([
                                'image/jpeg',
                                'image/png',
                                'image/webp',
                                'application/pdf',
                            ])
                            ->maxFiles(20),
                    ]),
            ]);
    }
}
