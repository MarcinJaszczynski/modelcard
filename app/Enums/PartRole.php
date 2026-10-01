<?php

namespace App\Enums;

enum PartRole: string
{
    case Unknown = 'unknown';
    case Hull = 'hull';
    case Flap = 'flap';
    case Form = 'form';
    case CutLine = 'cut_line';
    case FoldLine = 'fold_line';
    case Texture = 'texture';
    case Instruction = 'instruction';

    public function label(): string
    {
        return match ($this) {
            self::Unknown => 'Nieokreślone',
            self::Hull => 'Kadłub / bryła',
            self::Flap => 'Sklejka / zakładka',
            self::Form => 'Formierz / wzmocnienie',
            self::CutLine => 'Linia cięcia',
            self::FoldLine => 'Linia gięcia',
            self::Texture => 'Tekstura / markings',
            self::Instruction => 'Instrukcja',
        };
    }
}
