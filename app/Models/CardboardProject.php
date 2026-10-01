<?php

namespace App\Models;

use App\Enums\PrimitiveShape;
use App\Enums\ProjectStatus;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class CardboardProject extends Model
{
    protected $fillable = [
        'user_id',
        'name',
        'description',
        'status',
        'shape',
        'parameters',
        'scale',
        'model_type',
        'publisher',
        'year',
        'latest_svg_path',
        'latest_pdf_path',
    ];

    protected function casts(): array
    {
        return [
            'status' => ProjectStatus::class,
            'shape' => PrimitiveShape::class,
            'parameters' => 'array',
            'year' => 'integer',
        ];
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function assets(): HasMany
    {
        return $this->hasMany(ProjectAsset::class);
    }

    public function generationJobs(): HasMany
    {
        return $this->hasMany(GenerationJob::class);
    }

    /**
     * @return array<string, float|int|string>
     */
    public static function defaultBoxParameters(): array
    {
        return [
            'width_mm' => 80.0,
            'height_mm' => 50.0,
            'depth_mm' => 40.0,
            'flap_mm' => 8.0,
            'sheet' => 'A4',
            'style' => 'clean',
            'markings' => false,
            'multisheet' => false,
            'instructions' => true,
            'formers' => false,
            'former_thickness_mm' => 1.0,
            'series' => 'beginner',
            'scale' => '1:25',
            'profile' => 'express',
        ];
    }

    /**
     * @return array<string, float|int|string|bool>
     */
    public static function defaultCylinderParameters(): array
    {
        return [
            'diameter_mm' => 50.0,
            'height_mm' => 80.0,
            'flap_mm' => 8.0,
            'segments' => 24,
            'sheet' => 'A4',
            'style' => 'clean',
            'markings' => false,
            'multisheet' => false,
            'instructions' => true,
            'formers' => false,
            'former_thickness_mm' => 1.0,
            'series' => 'beginner',
            'scale' => '1:33',
        ];
    }

    /**
     * @return array<string, float|int|string|bool>
     */
    public static function defaultBuildingParameters(): array
    {
        return [
            'width_mm' => 80.0,
            'depth_mm' => 60.0,
            'wall_height_mm' => 45.0,
            'roof_rise_mm' => 25.0,
            'flap_mm' => 8.0,
            'sheet' => 'A4',
            'style' => 'clean',
            'markings' => true,
            'multisheet' => false,
            'instructions' => true,
            'formers' => true,
            'former_thickness_mm' => 1.0,
            'series' => 'beginner',
            'scale' => '1:25',
        ];
    }

    /**
     * @return array<string, float|int|string|bool>
     */
    public static function defaultWagonParameters(): array
    {
        return [
            'length_mm' => 100.0,
            'wagon_width_mm' => 40.0,
            'height_mm' => 35.0,
            'chassis_height_mm' => 8.0,
            'wheel_diameter_mm' => 18.0,
            'flap_mm' => 8.0,
            'sheet' => 'A4',
            'style' => 'clean',
            'markings' => true,
            'multisheet' => false,
            'instructions' => true,
            'formers' => true,
            'former_thickness_mm' => 1.0,
            'series' => 'beginner',
            'scale' => '1:87',
        ];
    }

    public function defaultParametersForShape(): array
    {
        return match ($this->shape) {
            PrimitiveShape::Cylinder => self::defaultCylinderParameters(),
            PrimitiveShape::Building => self::defaultBuildingParameters(),
            PrimitiveShape::Wagon => self::defaultWagonParameters(),
            PrimitiveShape::Fighter => self::defaultFighterParameters(),
            default => self::defaultBoxParameters(),
        };
    }

    /**
     * @return array<string, float|int|string|bool>
     */
    public static function defaultFighterParameters(): array
    {
        return [
            'fuselage_length_mm' => 205.0,
            'fuselage_diameter_mm' => 26.0,
            'wingspan_mm' => 235.0,
            'wing_chord_mm' => 36.0,
            'tailplane_span_mm' => 72.0,
            'tailplane_chord_mm' => 20.0,
            'fin_height_mm' => 30.0,
            'fin_chord_mm' => 26.0,
            'flap_mm' => 6.0,
            'sheet' => 'A4',
            'style' => 'dust',
            'markings' => false,
            'multisheet' => false,
            'instructions' => true,
            'formers' => true,
            'former_thickness_mm' => 1.0,
            'series' => 'standard',
            'scale' => '1:48',
            'profile' => 'magazine',
            'paint_scheme' => 'korea_45ths_polka',
            'min_part_mm' => 6.0,
        ];
    }

    public function resolvedParameters(): array
    {
        return array_merge($this->defaultParametersForShape(), $this->parameters ?? []);
    }
}
