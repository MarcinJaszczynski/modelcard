<?php

namespace App\Enums;

enum GenerationJobStatus: string
{
    case Pending = 'pending';
    case Queued = 'queued';
    case Running = 'running';
    case Succeeded = 'succeeded';
    case Failed = 'failed';

    public function label(): string
    {
        return match ($this) {
            self::Pending => 'Oczekuje',
            self::Queued => 'W kolejce',
            self::Running => 'W toku',
            self::Succeeded => 'Sukces',
            self::Failed => 'Błąd',
        };
    }
}
