<?php

namespace App\Enums;

enum SheetStyle: string
{
    case Clean = 'clean';
    case Dirt = 'dirt';
    case Rust = 'rust';
    case Dust = 'dust';

    public function label(): string
    {
        return match ($this) {
            self::Clean => 'Czysty druk',
            self::Dirt => 'Lekki brud',
            self::Rust => 'Rdza',
            self::Dust => 'Kurz / pył',
        };
    }
}
