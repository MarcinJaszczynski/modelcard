<?php

return [
    /*
    | Lokalna AI (LM Studio / OpenAI-compatible) — doradca stylu, nie źródło prawdy.
    */
    'enabled' => env('AI_ENABLED', true),

    'base_url' => env('AI_BASE_URL', 'http://127.0.0.1:1234/v1'),

    'api_key' => env('AI_API_KEY', 'lm-studio'),

    'timeout' => (int) env('AI_TIMEOUT', 45),

    'models' => [
        'chat' => env('AI_CHAT_MODEL', 'lmstudio-community/gemma-4-26b-a4b-it-qat-mlx'),
        'vision' => env('AI_VISION_MODEL', 'qwen/qwen3-vl-8b'),
        'embed' => env('AI_EMBED_MODEL', 'text-embedding-nomic-embed-text-v1.5'),
    ],

    /*
    | Krytyka stylu po generacji — opcjonalna, nie blokuje sukcesu joba.
    */
    'critique_after_generate' => env('AI_CRITIQUE_AFTER_GENERATE', false),

    /*
    | Lokalny generator obrazów (AUTOMATIC1111 / Forge) — opcjonalny.
    | Geometry-worker czyta AI_IMAGE_BASE_URL / AI_IMAGE_ENABLED ze środowiska.
    */
    'image_gen' => [
        'enabled' => env('AI_IMAGE_ENABLED', false),
        'base_url' => env('AI_IMAGE_BASE_URL', 'http://127.0.0.1:7860'),
    ],
];
