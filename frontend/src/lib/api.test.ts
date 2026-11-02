import { describe, expect, it, vi, afterEach } from 'vitest';
import { request } from './api';
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
      vi
        .fn()
        .mockResolvedValue(
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
});
