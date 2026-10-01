<?php

namespace App\Filament\Pages;

use App\Enums\ModelCategory;
use App\Enums\SheetStyle;
use App\Filament\Resources\CardboardProjects\CardboardProjectResource;
use App\Services\Geometry\AutoGenerationService;
use App\Services\Geometry\ModelTemplateLibrary;
use BackedEnum;
use Filament\Actions\Action;
use Filament\Forms\Components\FileUpload;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\TextInput;
use Filament\Forms\Components\Toggle;
use Filament\Notifications\Notification;
use Filament\Pages\Page;
use Filament\Schemas\Components\Actions;
use Filament\Schemas\Components\Component;
use Filament\Schemas\Components\EmbeddedSchema;
use Filament\Schemas\Components\Form;
use Filament\Schemas\Components\Section;
use Filament\Schemas\Schema;
use Filament\Support\Icons\Heroicon;
use Illuminate\Support\Facades\Storage;
use Livewire\Features\SupportFileUploads\TemporaryUploadedFile;
use Throwable;

/**
 * @property-read Schema $form
 */
class AutoGenerate extends Page
{
    protected static string|BackedEnum|null $navigationIcon = Heroicon::OutlinedSparkles;

    protected static ?string $navigationLabel = 'Auto generacja';

    protected static ?string $title = 'Automatyczne tworzenie modelu';

    protected static ?int $navigationSort = 2;

    /**
     * @var array<string, mixed>|null
     */
    public ?array $data = [];

    public function mount(): void
    {
        $this->form->fill([
            'category' => ModelCategory::Van->value,
            'scale' => null,
            'series' => null,
            'style' => null,
            'name' => null,
            'analyze_reference' => true,
            'auto_detect_category' => false,
            'size_factor' => 1.0,
        ]);
    }

    public function defaultForm(Schema $schema): Schema
    {
        return $schema->statePath('data');
    }

    public function form(Schema $schema): Schema
    {
        return $schema
            ->components([
                Section::make('Jeden klik → pełny zestaw')
                    ->description('Wybierz kategorię (lub pozwól CV zasugerować). Opcjonalnie dodaj zdjęcie/skan — pipeline dobierze szablon, warstwy, markings i wygeneruje SVG/PDF.')
                    ->columns(2)
                    ->schema([
                        Select::make('category')
                            ->label('Kategoria / szablon')
                            ->options(fn (ModelTemplateLibrary $lib): array => $lib->options())
                            ->required()
                            ->helperText('Preset Answer-like: wymiary, styl, markings, instrukcja, formierze.'),
                        TextInput::make('name')
                            ->label('Nazwa projektu (opcjonalnie)')
                            ->maxLength(255)
                            ->placeholder('np. Furgon Express auto'),
                        Select::make('scale')
                            ->label('Skala (nadpisz szablon)')
                            ->options(collect(config('modelarz.scales'))->mapWithKeys(
                                fn (array $meta, string $key) => [$key => $meta['label']]
                            ))
                            ->placeholder('Zostaw domyślną ze szablonu'),
                        Select::make('series')
                            ->label('Seria / poziom')
                            ->options(collect(config('modelarz.series'))->mapWithKeys(
                                fn (array $meta, string $key) => [$key => $meta['label']]
                            ))
                            ->placeholder('Zostaw domyślną ze szablonu'),
                        Select::make('style')
                            ->label('Styl weathering')
                            ->options(collect(SheetStyle::cases())->mapWithKeys(
                                fn (SheetStyle $s) => [$s->value => $s->label()]
                            ))
                            ->placeholder('Zostaw domyślny ze szablonu'),
                        TextInput::make('size_factor')
                            ->label('Współczynnik rozmiaru')
                            ->numeric()
                            ->minValue(0.6)
                            ->maxValue(1.6)
                            ->step(0.05)
                            ->default(1.0)
                            ->helperText('1.0 = rozmiar szablonu. CV może lekko skorygować.'),
                        Toggle::make('analyze_reference')
                            ->label('Analizuj referencję (CV → size factor)')
                            ->default(true),
                        Toggle::make('auto_detect_category')
                            ->label('Zasugeruj kategorię z referencji (heurystyka CV)')
                            ->default(false)
                            ->helperText('Wymaga uploadu. Nadpisze wybraną kategorię gdy heurystyka pewna.'),
                        FileUpload::make('reference')
                            ->label('Referencja (zdjęcie / skan)')
                            ->image()
                            ->disk('local')
                            ->directory('references/auto')
                            ->visibility('private')
                            ->acceptedFileTypes(['image/png', 'image/jpeg', 'image/webp'])
                            ->maxSize(12288)
                            ->columnSpanFull(),
                    ]),
            ]);
    }

    public function content(Schema $schema): Schema
    {
        return $schema
            ->components([
                $this->getFormContentComponent(),
            ]);
    }

    public function getFormContentComponent(): Component
    {
        return Form::make([EmbeddedSchema::make('form')])
            ->id('form')
            ->livewireSubmitHandler('generate')
            ->footer([
                Actions::make([
                    Action::make('generate')
                        ->label('Wygeneruj automatycznie')
                        ->icon(Heroicon::OutlinedSparkles)
                        ->color('primary')
                        ->submit('generate'),
                ])
                    ->alignment('start')
                    ->key('form-actions'),
            ]);
    }

    public function generate(AutoGenerationService $auto): void
    {
        $data = $this->form->getState();

        try {
            $result = $auto->run([
                'category' => $data['category'],
                'scale' => $data['scale'] ?: null,
                'series' => $data['series'] ?: null,
                'style' => $data['style'] ?: null,
                'name' => $data['name'] ?: null,
                'analyze_reference' => (bool) ($data['analyze_reference'] ?? true),
                'auto_detect_category' => (bool) ($data['auto_detect_category'] ?? false),
                'size_factor' => isset($data['size_factor']) ? (float) $data['size_factor'] : null,
                'reference' => $this->resolveReference($data['reference'] ?? null),
            ]);
        } catch (Throwable $e) {
            Notification::make()
                ->title('Generacja nie powiodła się')
                ->body($e->getMessage())
                ->danger()
                ->send();

            return;
        }

        $job = $result['job'];
        if ($job->status->value !== 'succeeded') {
            Notification::make()
                ->title('Job nie zakończył się sukcesem')
                ->body($job->error_message ?? 'Nieznany błąd')
                ->danger()
                ->send();

            return;
        }

        $analysisNote = '';
        if ($result['analysis'] ?? null) {
            $analysisNote = sprintf(
                ' CV: factor=%s, linii=%s.',
                $result['analysis']['size_factor'] ?? '?',
                $result['analysis']['line_count'] ?? '?',
            );
            if (! empty($result['analysis']['suggested_category'])) {
                $analysisNote .= ' Sugestia: '.$result['analysis']['suggested_category'].'.';
            }
        }

        Notification::make()
            ->title('Model wygenerowany')
            ->body('Projekt #'.$result['project']->id.' — '.$result['resolved']['meta']['label'].'.'.$analysisNote)
            ->success()
            ->send();

        $this->redirect(
            CardboardProjectResource::getUrl('view', ['record' => $result['project']]),
        );
    }

    private function resolveReference(mixed $value): TemporaryUploadedFile|string|null
    {
        if ($value instanceof TemporaryUploadedFile) {
            return $value;
        }

        if (is_array($value)) {
            $value = $value[0] ?? null;
        }

        if (! is_string($value) || $value === '') {
            return null;
        }

        if (Storage::disk('local')->exists($value)) {
            return $value;
        }

        return null;
    }
}
