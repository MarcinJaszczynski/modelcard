<?php

namespace App\Filament\Resources\CardboardProjects;

use App\Filament\Resources\CardboardProjects\Pages\CreateCardboardProject;
use App\Filament\Resources\CardboardProjects\Pages\EditCardboardProject;
use App\Filament\Resources\CardboardProjects\Pages\ListCardboardProjects;
use App\Filament\Resources\CardboardProjects\Pages\ViewCardboardProject;
use App\Filament\Resources\CardboardProjects\RelationManagers\AssetsRelationManager;
use App\Filament\Resources\CardboardProjects\RelationManagers\GenerationJobsRelationManager;
use App\Filament\Resources\CardboardProjects\Schemas\CardboardProjectForm;
use App\Filament\Resources\CardboardProjects\Schemas\CardboardProjectInfolist;
use App\Filament\Resources\CardboardProjects\Tables\CardboardProjectsTable;
use App\Models\CardboardProject;
use BackedEnum;
use Filament\Resources\Resource;
use Filament\Schemas\Schema;
use Filament\Support\Icons\Heroicon;
use Filament\Tables\Table;

class CardboardProjectResource extends Resource
{
    protected static ?string $model = CardboardProject::class;

    protected static ?string $recordTitleAttribute = 'name';

    protected static ?string $navigationLabel = 'Projekty kartonowe';

    protected static ?string $modelLabel = 'projekt kartonowy';

    protected static ?string $pluralModelLabel = 'projekty kartonowe';

    protected static string|BackedEnum|null $navigationIcon = Heroicon::OutlinedRectangleStack;

    public static function form(Schema $schema): Schema
    {
        return CardboardProjectForm::configure($schema);
    }

    public static function infolist(Schema $schema): Schema
    {
        return CardboardProjectInfolist::configure($schema);
    }

    public static function table(Table $table): Table
    {
        return CardboardProjectsTable::configure($table);
    }

    public static function getRelations(): array
    {
        return [
            AssetsRelationManager::class,
            GenerationJobsRelationManager::class,
        ];
    }

    public static function getPages(): array
    {
        return [
            'index' => ListCardboardProjects::route('/'),
            'create' => CreateCardboardProject::route('/create'),
            'view' => ViewCardboardProject::route('/{record}'),
            'edit' => EditCardboardProject::route('/{record}/edit'),
        ];
    }
}
