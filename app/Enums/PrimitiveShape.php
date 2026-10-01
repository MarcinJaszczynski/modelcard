<?php

namespace App\Enums;

enum PrimitiveShape: string
{
    case Box = 'box';
    case Cylinder = 'cylinder';
    case Building = 'building';
    case Wagon = 'wagon';
    case Fighter = 'fighter';

    public function label(): string
    {
        return match ($this) {
            self::Box => 'Prostopadłościan',
            self::Cylinder => 'Walec / tuba',
            self::Building => 'Budynek (dach dwuspadowy)',
            self::Wagon => 'Wagon towarowy',
            self::Fighter => 'Myśliwiec (uproszczony)',
        };
    }
}
