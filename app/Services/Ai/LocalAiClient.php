<?php

namespace App\Services\Ai;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Throwable;

/**
 * Klient lokalnej AI (LM Studio — OpenAI-compatible).
 * Używany do krytki stylu / doradztwa, nie do kopiowania plansz.
 */
class LocalAiClient
{
    public function enabled(): bool
    {
        return (bool) config('ai.enabled', true);
    }

    public function chat(string $system, string $user, ?string $model = null): ?string
    {
        if (! $this->enabled()) {
            return null;
        }

        try {
            $response = Http::baseUrl(rtrim((string) config('ai.base_url'), '/'))
                ->withToken((string) config('ai.api_key'))
                ->timeout((int) config('ai.timeout', 45))
                ->acceptJson()
                ->post('/chat/completions', [
                    'model' => $model ?: config('ai.models.chat'),
                    'temperature' => 0.2,
                    'max_tokens' => 600,
                    'messages' => [
                        ['role' => 'system', 'content' => $system],
                        ['role' => 'user', 'content' => $user],
                    ],
                ]);

            if (! $response->successful()) {
                Log::warning('Local AI chat failed', [
                    'status' => $response->status(),
                    'body' => $response->body(),
                ]);

                return null;
            }

            return $response->json('choices.0.message.content');
        } catch (Throwable $e) {
            Log::warning('Local AI unavailable: '.$e->getMessage());

            return null;
        }
    }
}
