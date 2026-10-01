<?php

namespace App\Filament\Resources\CardboardProjects\RelationManagers;

use App\Enums\AssetType;
use App\Enums\PartRole;
use App\Services\Geometry\ScanAnalysisService;
use Filament\Actions\Action;
use Filament\Actions\BulkActionGroup;
use Filament\Actions\DeleteAction;
use Filament\Actions\DeleteBulkAction;
use Filament\Actions\EditAction;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\TagsInput;
use Filament\Forms\Components\Textarea;
use Filament\Forms\Components\TextInput;
use Filament\Notifications\Notification;
use Filament\Resources\RelationManagers\RelationManager;
use Filament\Schemas\Schema;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Table;
use Illuminate\Support\Facades\Storage;
use Throwable;

class AssetsRelationManager extends RelationManager
{
    protected static string $relationship = 'assets';

    protected static ?string $title = 'Materiały / assety (korpus)';

    public function form(Schema $schema): Schema
    {
        return $schema
            ->components([
                Select::make('type')
                    ->label('Typ pliku')
                    ->options(collect(AssetType::cases())->mapWithKeys(
                        fn (AssetType $t) => [$t->value => $t->label()]
                    ))
                    ->required(),
                Select::make('part_role')
                    ->label('Rola / annotacja strukturalna')
                    ->options(collect(PartRole::cases())->mapWithKeys(
                        fn (PartRole $r) => [$r->value => $r->label()]
                    ))
                    ->default(PartRole::Unknown->value),
                TagsInput::make('tags')
                    ->label('Tagi')
                    ->placeholder('np. kadłub, sklejka, whethering'),
                Textarea::make('annotation')
                    ->label('Notatka annotacyjna')
                    ->rows(3)
                    ->helperText('np. „to jest część kadłuba”, „linia gięcia”, „sklejka”'),
                TextInput::make('original_name')
                    ->label('Nazwa pliku')
                    ->disabled(),
            ]);
    }

    public function table(Table $table): Table
    {
        return $table
            ->columns([
                TextColumn::make('type')
                    ->label('Typ')
                    ->badge()
                    ->formatStateUsing(fn ($state) => $state instanceof AssetType ? $state->label() : (string) $state),
                TextColumn::make('part_role')
                    ->label('Rola')
                    ->formatStateUsing(fn ($state) => $state instanceof PartRole ? $state->label() : ($state ?: '—')),
                TextColumn::make('tags')
                    ->label('Tagi')
                    ->badge()
                    ->separator(',')
                    ->placeholder('—'),
                TextColumn::make('annotation')
                    ->label('Annotacja')
                    ->limit(40)
                    ->placeholder('—'),
                TextColumn::make('original_name')
                    ->label('Plik')
                    ->searchable(),
                TextColumn::make('created_at')
                    ->label('Dodano')
                    ->dateTime('Y-m-d H:i'),
            ])
            ->headerActions([])
            ->recordActions([
                Action::make('analyzeScan')
                    ->label('Analizuj skan')
                    ->icon('heroicon-o-magnifying-glass-circle')
                    ->color('warning')
                    ->requiresConfirmation()
                    ->modalHeading('Analiza CV skanu')
                    ->modalDescription('Wykryje linie i zaproponuje cut/fold. To tylko sugestie — wymagają ręcznej weryfikacji.')
                    ->visible(fn ($record) => $record->type instanceof AssetType
                        && $record->type->isAnalyzable()
                        && Storage::disk($record->disk)->exists($record->path))
                    ->action(function ($record, ScanAnalysisService $service): void {
                        try {
                            $out = $service->analyze($record);
                            Notification::make()
                                ->title('Analiza gotowa')
                                ->body(sprintf(
                                    'Wykryto %d linii (cut=%d, fold=%d). Overlay zapisany jako nowy asset.',
                                    $out['result']['line_count'] ?? 0,
                                    $out['result']['cut_count'] ?? 0,
                                    $out['result']['fold_count'] ?? 0,
                                ))
                                ->success()
                                ->send();
                        } catch (Throwable $e) {
                            Notification::make()
                                ->title('Analiza nie powiodła się')
                                ->body($e->getMessage())
                                ->danger()
                                ->send();
                        }
                    }),
                EditAction::make(),
                DeleteAction::make(),
            ])
            ->toolbarActions([
                BulkActionGroup::make([
                    DeleteBulkAction::make(),
                ]),
            ]);
    }
}
