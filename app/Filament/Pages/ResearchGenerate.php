<?php

namespace App\Filament\Pages;

use App\Filament\Resources\CardboardProjects\CardboardProjectResource;
use App\Services\Geometry\AutoGenerationService;
use App\Services\Research\SubjectResearchService;
use BackedEnum;
use Filament\Actions\Action;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\TextInput;
use Filament\Notifications\Notification;
use Filament\Pages\Page;
use Filament\Schemas\Components\Actions;
use Filament\Schemas\Components\Component;
use Filament\Schemas\Components\EmbeddedSchema;
use Filament\Schemas\Components\Form;
use Filament\Schemas\Components\Section;
use Filament\Schemas\Schema;
use Filament\Support\Icons\Heroicon;
use Throwable;

/**
 * @property-read Schema $form
 */
class ResearchGenerate extends Page
{
    protected static string|BackedEnum|null $navigationIcon = Heroicon::OutlinedMagnifyingGlass;

    protected static ?string $navigationLabel = 'Wyszukaj wzorzec';

    protected static ?string $title = 'Wyszukaj wzorzec → schemat → wycinanka';

    protected static ?int $navigationSort = 1;

    /**
     * @var array<string, mixed>|null
     */
    public ?array $data = [];

    /**
     * @var array<string, mixed>|null
     */
    public ?array $research = null;

    public function mount(): void
    {
        $this->form->fill([
            'query' => 'p51 mustang korea',
            'scheme' => null,
            'scale' => null,
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
                Section::make('Wyszukiwanie')
                    ->description('np. „p51 mustang korea”, „f-51 45th trs”. Dostajesz schematy malowania i wskazówki, potem generujesz oteksturowaną wycinankę.')
                    ->schema([
                        TextInput::make('query')
                            ->label('Wzorzec / temat')
                            ->required()
                            ->maxLength(255),
                        Select::make('scheme')
                            ->label('Schemat malowania')
                            ->options(fn (): array => collect($this->research['schemes'] ?? [])
                                ->mapWithKeys(fn (array $s) => [$s['key'] => $s['label']])
                                ->all())
                            ->visible(fn (): bool => filled($this->research['schemes'] ?? null))
                            ->helperText(fn (): ?string => $this->research['subject']['summary'] ?? null),
                        Select::make('scale')
                            ->label('Skala')
                            ->options(collect(config('modelarz.scales'))->mapWithKeys(
                                fn (array $meta, string $key) => [$key => $meta['label']]
                            ))
                            ->placeholder('Domyślna z researchu'),
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
            ->footer([
                Actions::make([
                    Action::make('search')
                        ->label('Szukaj schematów')
                        ->color('gray')
                        ->action('search'),
                    Action::make('generate')
                        ->label('Generuj wycinankę')
                        ->icon(Heroicon::OutlinedSparkles)
                        ->color('primary')
                        ->disabled(fn (): bool => blank($this->research['recommended_template'] ?? null))
                        ->action('generate'),
                ])->alignment('start'),
            ]);
    }

    public function search(SubjectResearchService $research): void
    {
        $query = (string) ($this->form->getState()['query'] ?? '');
        $this->research = $research->search($query);

        if (! ($this->research['subject'] ?? null)) {
            Notification::make()
                ->title('Brak dopasowania')
                ->body($this->research['kit_hints'][0] ?? '')
                ->warning()
                ->send();

            return;
        }

        $defaultScheme = $this->research['schemes'][0]['key'] ?? null;
        $this->form->fill([
            ...$this->form->getState(),
            'scheme' => $defaultScheme,
            'scale' => $this->research['recommended_scale'],
        ]);

        Notification::make()
            ->title($this->research['subject']['label'])
            ->body(count($this->research['schemes']).' schemat(y) malowania')
            ->success()
            ->send();
    }

    public function generate(AutoGenerationService $auto): void
    {
        if (! ($this->research['recommended_template'] ?? null)) {
            $this->search(app(SubjectResearchService::class));
        }

        if (! ($this->research['recommended_template'] ?? null)) {
            Notification::make()->title('Najpierw wyszukaj wzorzec')->warning()->send();

            return;
        }

        $data = $this->form->getState();

        try {
            $result = $auto->run([
                'category' => $this->research['recommended_template'],
                'scale' => $data['scale'] ?: $this->research['recommended_scale'],
                'paint_scheme' => $data['scheme'] ?: ($this->research['schemes'][0]['key'] ?? null),
                'name' => ($this->research['subject']['label'] ?? 'Research').' / '.($data['scheme'] ?? ''),
                'analyze_reference' => false,
            ]);
        } catch (Throwable $e) {
            Notification::make()->title('Błąd generacji')->body($e->getMessage())->danger()->send();

            return;
        }

        if ($result['job']->status->value !== 'succeeded') {
            Notification::make()
                ->title('Job failed')
                ->body($result['job']->error_message ?? '')
                ->danger()
                ->send();

            return;
        }

        Notification::make()
            ->title('Wycinanka gotowa')
            ->body('Projekt #'.$result['project']->id)
            ->success()
            ->send();

        $this->redirect(CardboardProjectResource::getUrl('view', ['record' => $result['project']]));
    }
}
