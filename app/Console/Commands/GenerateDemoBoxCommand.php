<?php

namespace App\Console\Commands;

use App\Enums\PrimitiveShape;
use App\Enums\ProjectStatus;
use App\Models\CardboardProject;
use App\Models\User;
use App\Services\Geometry\GenerationDispatcher;
use Illuminate\Console\Command;

class GenerateDemoBoxCommand extends Command
{
    protected $signature = 'modelarz:demo-box
        {--shape=box : box|cylinder|building|wagon}
        {--style=clean : clean|dirt|rust|dust}
        {--markings=1 : 1/0 markings}
        {--multisheet=0 : 1/0 wymuś wiele arkuszy}
        {--formers=1 : 1/0 formierze}
        {--instructions=1 : 1/0 instrukcja}
        {--width=80 : Szerokość mm}
        {--height=50 : Wysokość mm}
        {--depth=40 : Głębokość mm}
        {--diameter=50 : Średnica mm (cylinder)}
        {--length=100 : Długość (wagon)}
        {--wagon-width=40 : Szerokość (wagon)}
        {--wall=45 : Wysokość ściany (building)}
        {--roof=25 : Wznios dachu (building)}
        {--flap=8 : Zakładka mm}
        {--sheet=A4 : Arkusz}';

    protected $description = 'End-to-end: bryła → SVG + PDF na arkuszu';

    public function handle(GenerationDispatcher $dispatcher): int
    {
        $user = User::query()->first();
        $shape = PrimitiveShape::tryFrom((string) $this->option('shape')) ?? PrimitiveShape::Box;
        $style = (string) $this->option('style');
        $markings = filter_var($this->option('markings'), FILTER_VALIDATE_BOOLEAN);
        $multisheet = filter_var($this->option('multisheet'), FILTER_VALIDATE_BOOLEAN);
        $formers = filter_var($this->option('formers'), FILTER_VALIDATE_BOOLEAN);
        $instructions = filter_var($this->option('instructions'), FILTER_VALIDATE_BOOLEAN);

        $common = [
            'flap_mm' => (float) $this->option('flap'),
            'sheet' => (string) $this->option('sheet'),
            'style' => $style,
            'markings' => $markings,
            'multisheet' => $multisheet,
            'formers' => $formers,
            'instructions' => $instructions,
            'former_thickness_mm' => 1.0,
            'series' => 'beginner',
            'scale' => '1:25',
        ];

        $parameters = match ($shape) {
            PrimitiveShape::Cylinder => array_merge($common, [
                'diameter_mm' => (float) $this->option('diameter'),
                'height_mm' => (float) $this->option('height'),
                'segments' => 24,
                'scale' => '1:33',
                'markings' => false,
            ]),
            PrimitiveShape::Building => array_merge($common, [
                'width_mm' => (float) $this->option('width'),
                'depth_mm' => (float) $this->option('depth'),
                'wall_height_mm' => (float) $this->option('wall'),
                'roof_rise_mm' => (float) $this->option('roof'),
            ]),
            PrimitiveShape::Wagon => array_merge($common, [
                'length_mm' => (float) $this->option('length'),
                'wagon_width_mm' => (float) $this->option('wagon-width'),
                'height_mm' => (float) $this->option('height'),
                'chassis_height_mm' => 8.0,
                'wheel_diameter_mm' => 18.0,
                'scale' => '1:87',
            ]),
            default => array_merge($common, [
                'width_mm' => (float) $this->option('width'),
                'height_mm' => (float) $this->option('height'),
                'depth_mm' => (float) $this->option('depth'),
                'markings' => false,
            ]),
        };

        $project = CardboardProject::query()->create([
            'user_id' => $user?->id,
            'name' => 'Demo '.$shape->label().' / '.$style.' '.now()->format('Y-m-d H:i:s'),
            'description' => 'Wygenerowane przez modelarz:demo-box',
            'status' => ProjectStatus::Draft,
            'shape' => $shape,
            'parameters' => $parameters,
        ]);

        $job = $dispatcher->dispatchSync($project);

        if ($job->status->value !== 'succeeded') {
            $this->error($job->error_message ?? 'Generowanie nie powiodło się');

            return self::FAILURE;
        }

        $this->info('OK — projekt #'.$project->id.' ('.$shape->label().', styl: '.$style.')');
        $this->line('SVG: '.$job->output_svg_path);
        $this->line('PDF: '.$job->output_pdf_path);
        $pages = $job->result_payload['page_count'] ?? 1;
        $this->line('Strony: '.$pages.(($job->result_payload['multisheet'] ?? false) ? ' (multisheet)' : ''));

        return self::SUCCESS;
    }
}
