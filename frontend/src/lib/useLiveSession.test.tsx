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
class SocketStub {
  static OPEN = 1;
  static latest: SocketStub;
  readyState = 1;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  constructor() {
    SocketStub.latest = this;
  }
  send = vi.fn();
  close() {
    this.readyState = 3;
    this.onclose?.();
  }
  receive(type: string, payload: unknown) {
    this.onmessage?.({ data: JSON.stringify({ version: 1, type, payload }) });
  }
}
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
  it('does not let a delayed initial fetch roll back a newer socket snapshot', async () => {
    vi.stubGlobal('WebSocket', SocketStub);
    let resolveLoad!: (value: Session) => void;
    vi.spyOn(api, 'session').mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveLoad = resolve;
        }),
    );
    const { result } = renderHook(() => useLiveSession('s1'));
    act(() => SocketStub.latest.receive('session', { ...session, current_question: 2 }));
    expect(result.current.session?.current_question).toBe(2);
    await act(async () => {
      resolveLoad(session);
    });
    expect(result.current.session?.current_question).toBe(2);
  });
  it('restores both session and visible state after a dropped socket', async () => {
    vi.stubGlobal('WebSocket', SocketStub);
    vi.spyOn(api, 'session')
      .mockResolvedValueOnce(session)
      .mockResolvedValueOnce({ ...session, state: 'paused' });
    const { result } = renderHook(() => useLiveSession('s1'));
    await waitFor(() => expect(result.current.session?.id).toBe('s1'));
    act(() => SocketStub.latest.receive('session', session));
    await act(async () => {
      await result.current.answer({
        transcript: 'My draft',
        language: 'en-HK',
        elapsed_seconds: 30,
        corrected: false,
      });
    });
    act(() => {
      SocketStub.latest.receive('state', { state: 'thinking' });
      SocketStub.latest.close();
    });
    await waitFor(() => expect(result.current.session?.state).toBe('paused'));
    expect(result.current.state).toBe('paused');
    expect(result.current.busy).toBe(false);
  });
  it('keeps the HTTP result when a socket handshake arrives after fallback submission', async () => {
    vi.stubGlobal('WebSocket', SocketStub);
    vi.spyOn(api, 'session').mockResolvedValue(session);
    vi.spyOn(api, 'answer').mockResolvedValue({ ...session, current_question: 2 });
    const { result } = renderHook(() => useLiveSession('s1'));
    await waitFor(() => expect(result.current.session?.id).toBe('s1'));
    SocketStub.latest.readyState = 0;
    await act(async () => {
      await result.current.answer({
        transcript: 'My answer',
        language: 'en-HK',
        elapsed_seconds: 10,
        corrected: false,
      });
    });
    act(() => SocketStub.latest.receive('session', session));
    expect(result.current.session?.current_question).toBe(2);
  });
});
