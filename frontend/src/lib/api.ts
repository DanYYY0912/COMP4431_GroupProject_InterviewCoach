import { z } from 'zod';
import { profileSchema, reportSchema, sessionSchema } from './types';
import type { Answer, ControlAction, Health, Language, Methodology } from './types';

export async function request<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: 'The local service could not complete this request.' }));
    const detail =
      typeof body.detail === 'string'
        ? body.detail
        : Array.isArray(body.detail)
          ? body.detail.map((item: { msg?: string }) => item.msg).join('; ')
          : 'The local service could not complete this request.';
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

const post = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) });
export const api = {
  health: () => request<Health>('/api/health'),
  methodology: () => request<Methodology>('/api/methodology/metrics'),
  sessions: async () => z.array(sessionSchema).parse(await request('/api/sessions')),
  session: async (id: string) =>
    sessionSchema.parse(await request(`/api/sessions/${encodeURIComponent(id)}`)),
  profile: async (text: string, file: File | null) => {
    const form = new FormData();
    if (file) form.append('file', file);
    return profileSchema.parse(
      await request('/api/job-profiles', file ? { method: 'POST', body: form } : post({ text })),
    );
  },
  create: async (
    job_profile_id: string,
    language: Language,
    difficulty: string,
    question_count: number,
  ) =>
    sessionSchema.parse(
      await request(
        '/api/sessions',
        post({ job_profile_id, language, difficulty, question_count, store_transcript: true }),
      ),
    ),
  answer: async (id: string, answer: Answer) =>
    sessionSchema.parse(
      await request(`/api/sessions/${encodeURIComponent(id)}/answer`, post(answer)),
    ),
  control: async (id: string, action: ControlAction) =>
    sessionSchema.parse(
      await request(`/api/sessions/${encodeURIComponent(id)}/control`, post({ action })),
    ),
  report: async (id: string) =>
    reportSchema.parse(await request(`/api/sessions/${encodeURIComponent(id)}/report`)),
  delete: (id: string) => request(`/api/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  token: () =>
    request<{ token: string; region: string; expires_in: number }>(
      '/api/speech/token',
      post({ consent: true }),
    ),
  transcribe: (file: Blob, language: Language) => {
    const form = new FormData();
    form.append('file', file, 'answer.wav');
    form.append('language', language);
    return request<{ text: string; provider: string }>('/api/speech/transcribe', {
      method: 'POST',
      body: form,
    });
  },
};

export const errorMessage = (error: unknown) =>
  error instanceof z.ZodError
    ? 'The service returned an invalid response. Your answer has not been discarded; please try again.'
    : error instanceof Error
      ? error.message
      : 'Something went wrong. Please try again.';
