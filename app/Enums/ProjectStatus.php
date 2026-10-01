<?php

namespace App\Enums;

enum ProjectStatus: string
{
    case Draft = 'draft';
    case Ready = 'ready';
    case Generating = 'generating';
    case Completed = 'completed';
    case Failed = 'failed';

    public function label(): string
    {
        return match ($this) {
            self::Draft => 'Szkic',
            self::Ready => 'Gotowy',
            self::Generating => 'Generowanie',
            self::Completed => 'Ukończony',
            self::Failed => 'Błąd',
        };
    }
}
