import { describe, expect, it, vi, afterEach } from 'vitest';
import { api, request } from './api';
import { answerSchema, sessionSchema } from './types';

afterEach(() => vi.unstubAllGlobals());
describe('API boundary', () => {
  it('rejects malformed turns rather than displaying unvalidated model output', () => {
    expect(() =>
      sessionSchema.parse({ id: 'session', turns: [{ question: 'invalid' }] }),
    ).toThrow();
  });
  it('reports a readable validation error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: [{ loc: ['body', 'text'], msg: 'String should have at least 40 characters' }],
          }),
          { status: 422 },
        ),
      ),
    );
    await expect(request('/api/job-profiles')).rejects.toThrow(
      'String should have at least 40 characters',
    );
  });
  it('handles deletion without requiring JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(request('/api/sessions/one', { method: 'DELETE' })).resolves.toBeUndefined();
  });
  it('accepts absent audio measurements serialized as null by the API', () => {
    expect(
      answerSchema.parse({
        transcript: 'Typed answer',
        language: 'en-HK',
        elapsed_seconds: 10,
        corrected: false,
        turn_id: null,
        speech_metrics: null,
      }).speech_metrics,
    ).toBeNull();
  });
  it('accepts only redacted inference fields and sends model discovery through the app server', async () => {
    const service = {
      base_url: 'http://localhost:8001/v1',
      model: 'coach',
      api_key_set: true,
      api_key: 'must-not-reach-form',
    };
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ agent: service, asr: service, embedding: service, reranker: service }),
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ models: ['coach'] })));
    vi.stubGlobal('fetch', fetch);
    expect((await api.inferenceSettings()).agent).toEqual({
      base_url: service.base_url,
      model: 'coach',
      api_key_set: true,
    });
    await expect(
      api.inferenceModels('agent', { base_url: service.base_url, api_key: null }),
    ).resolves.toEqual({ models: ['coach'] });
    expect(fetch.mock.calls[1]).toEqual([
      '/api/inference-settings/agent/models',
      {
        method: 'POST',
        body: JSON.stringify({ base_url: service.base_url, api_key: null }),
        headers: { 'Content-Type': 'application/json' },
      },
    ]);
  });
});
