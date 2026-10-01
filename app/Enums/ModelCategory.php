<?php

namespace App\Enums;

enum ModelCategory: string
{
    case Van = 'van';
    case Tractor = 'tractor';
    case House = 'house';
    case FreightWagon = 'freight_wagon';
    case Silo = 'silo';
    case Crate = 'crate';
    case P51Korea = 'p51_korea';

    public function label(): string
    {
        return match ($this) {
            self::Van => 'Furgon / van (1:25)',
            self::Tractor => 'Ciągnik / bryła (1:25)',
            self::House => 'Budynek / domek',
            self::FreightWagon => 'Wagon towarowy',
            self::Silo => 'Silos / zbiornik',
            self::Crate => 'Skrzynia / prostopadłościan',
            self::P51Korea => 'F-51D Mustang Korea (1:48)',
        };
    }
}
