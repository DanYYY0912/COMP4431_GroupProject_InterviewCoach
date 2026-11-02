import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useLiveSession } from './useLiveSession';
import { api } from './api';
import type { Session } from './types';

const session: Session = {
  id: 's1',
  job_profile_id: 'j1',
  role_title: 'Engineer',
  language: 'en-HK',
  difficulty: 'standard',
  question_count: 3,
  state: 'ready',
  current_question: 1,
  turns: [
    {
      id: 't1',
      question: {
        interviewer_text: 'Describe a project.',
        question_type: 'opening',
        targeted_competencies: [],
        adaptive_follow_up_reason: null,
        citations: [],
      },
      answer: null,
      created_at: '2026-11-02T12:00:00Z',
    },
  ],
  created_at: '2026-11-02T12:00:00Z',
  provider: 'demo',
};
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
describe('live session recovery', () => {
  it('falls back to HTTP when no websocket is available and locks duplicate sends', async () => {
    vi.stubGlobal('WebSocket', undefined);
    vi.spyOn(api, 'session').mockResolvedValue(session);
    let resolveAnswer!: (value: Session) => void;
    const send = vi.spyOn(api, 'answer').mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveAnswer = resolve;
        }),
    );
    const { result } = renderHook(() => useLiveSession('s1'));
    await waitFor(() => expect(result.current.session?.id).toBe('s1'));
    const answer = {
      transcript: 'A specific project.',
      language: 'en-HK' as const,
      elapsed_seconds: 30,
      corrected: false,
      turn_id: 't1',
    };
    let pending: Promise<void>;
    act(() => {
      pending = result.current.answer(answer);
      void result.current.answer(answer);
    });
    expect(send).toHaveBeenCalledTimes(1);
    expect(result.current.busy).toBe(true);
    await act(async () => {
      resolveAnswer({ ...session, state: 'completed' });
      await pending;
    });
    expect(result.current.session?.state).toBe('completed');
    expect(result.current.busy).toBe(false);
  });
  it('can pause during a slow answer and ignores a late response from that answer', async () => {
    vi.stubGlobal('WebSocket', undefined);
    vi.spyOn(api, 'session').mockResolvedValue(session);
    let resolveAnswer!: (value: Session) => void;
    vi.spyOn(api, 'answer').mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveAnswer = resolve;
        }),
    );
    const control = vi.spyOn(api, 'control').mockResolvedValue({ ...session, state: 'paused' });
    const { result } = renderHook(() => useLiveSession('s1'));
    await waitFor(() => expect(result.current.session?.id).toBe('s1'));
    let pending: Promise<void>;
    act(() => {
      pending = result.current.answer({
        transcript: 'My answer',
        language: 'en-HK',
        elapsed_seconds: 20,
        corrected: false,
      });
    });
    await act(async () => {
      await result.current.control('pause');
    });
    expect(control).toHaveBeenCalledWith('s1', 'pause');
    expect(result.current.session?.state).toBe('paused');
    await act(async () => {
      resolveAnswer({ ...session, state: 'ready' });
      await pending;
    });
    expect(result.current.session?.state).toBe('paused');
  });
});
