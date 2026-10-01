<?php

namespace App\Filament\Resources\CardboardProjects\Pages;

use App\Filament\Resources\CardboardProjects\CardboardProjectResource;
use Filament\Actions\CreateAction;
use Filament\Resources\Pages\ListRecords;

class ListCardboardProjects extends ListRecords
{
    protected static string $resource = CardboardProjectResource::class;

    protected function getHeaderActions(): array
    {
        return [
            CreateAction::make(),
        ];
    }
}
