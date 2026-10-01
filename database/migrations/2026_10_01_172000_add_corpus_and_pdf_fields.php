<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('cardboard_projects', function (Blueprint $table) {
            $table->string('model_type')->nullable()->after('scale');
            $table->string('publisher')->nullable()->after('model_type');
            $table->unsignedSmallInteger('year')->nullable()->after('publisher');
            $table->string('latest_pdf_path')->nullable()->after('latest_svg_path');
        });

        Schema::table('project_assets', function (Blueprint $table) {
            $table->string('part_role')->nullable()->after('type');
            $table->json('tags')->nullable()->after('part_role');
            $table->text('annotation')->nullable()->after('tags');
        });

        Schema::table('generation_jobs', function (Blueprint $table) {
            $table->string('output_pdf_path')->nullable()->after('output_svg_path');
        });
    }

    public function down(): void
    {
        Schema::table('cardboard_projects', function (Blueprint $table) {
            $table->dropColumn(['model_type', 'publisher', 'year', 'latest_pdf_path']);
        });

        Schema::table('project_assets', function (Blueprint $table) {
            $table->dropColumn(['part_role', 'tags', 'annotation']);
        });

        Schema::table('generation_jobs', function (Blueprint $table) {
            $table->dropColumn('output_pdf_path');
        });
    }
};
