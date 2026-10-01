<?php

namespace App\Enums;

enum AssetType: string
{
    case Scan = 'scan';
    case Photo = 'photo';
    case Drawing = 'drawing';
    case Reference = 'reference';
    case OutputSvg = 'output_svg';
    case OutputPdf = 'output_pdf';
    case AnalysisOverlay = 'analysis_overlay';
    case AnalysisJson = 'analysis_json';
    case Instructions = 'instructions';
    case Formers = 'formers';

    public function label(): string
    {
        return match ($this) {
            self::Scan => 'Skan planszy',
            self::Photo => 'Zdjęcie',
            self::Drawing => 'Rysunek',
            self::Reference => 'Referencja',
            self::OutputSvg => 'Wynik SVG',
            self::OutputPdf => 'Wynik PDF',
            self::AnalysisOverlay => 'Overlay analizy CV',
            self::AnalysisJson => 'Sugestie CV (JSON)',
            self::Instructions => 'Instrukcja montażu',
            self::Formers => 'Formierze / szkielet',
        };
    }

    public function isAnalyzable(): bool
    {
        return in_array($this, [
            self::Scan,
            self::Photo,
            self::Drawing,
            self::Reference,
        ], true);
    }
}
