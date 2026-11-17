import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Interview } from './Interview';
import { useLiveSession } from '../lib/useLiveSession';
import { recordMicrophone, playQuestion } from '../lib/audio';
import type { Session } from '../lib/types';
import { api } from '../lib/api';

vi.mock('../lib/useLiveSession', () => ({ useLiveSession: vi.fn() }));
vi.mock('../lib/audio', () => ({
  recordMicrophone: vi.fn(),
  playQuestion: vi.fn(() => vi.fn()),
}));
vi.mock('../components/InterviewerPortrait', () => ({
  InterviewerPortrait: () => <div>Coach portrait</div>,
}));

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
        interviewer_text: 'Tell me about a project.',
        question_type: 'opening',
        targeted_competencies: [],
        adaptive_follow_up_reason: null,
        citations: [],
      },
      answer: null,
      created_at: '2026-11-02T00:00:00Z',
    },
  ],
  created_at: '2026-11-02T00:00:00Z',
  provider: 'demo',
};
const control = vi.fn().mockResolvedValue(undefined);
afterEach(() => vi.restoreAllMocks());
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useLiveSession).mockReturnValue({
    session,
    busy: false,
    error: '',
    setError: vi.fn(),
    state: 'ready',
    streamText: '',
    answer: vi.fn(),
    control,
  });
});

describe('microphone permission recovery', () => {
  it('preserves a typed draft when microphone permission is denied', async () => {
    vi.mocked(recordMicrophone).mockRejectedValue(new Error('Permission denied'));
    render(<Interview id="s1" navigate={vi.fn()} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Your answer'), 'My existing project story');
    await user.click(screen.getByRole('button', { name: 'Re-record answer' }));
    await screen.findByText(
      'Microphone access is unavailable. Type your answer below to continue.',
    );
    expect(screen.getByLabelText('Your answer')).toHaveValue('My existing project story');
  });
  it('closes late microphone access when the user paused during the permission prompt', async () => {
    let resolveCapture!: (value: Awaited<ReturnType<typeof recordMicrophone>>) => void;
    vi.mocked(recordMicrophone).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCapture = resolve;
        }),
    );
    const stop = vi
      .fn()
      .mockResolvedValue({ blob: new Blob(), duration: 0, pauseCount: 0, silenceSeconds: 0 });
    render(<Interview id="s1" navigate={vi.fn()} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Record answer' }));
    await user.click(screen.getByRole('button', { name: /^Pause$/ }));
    await act(async () => {
      resolveCapture({ stream: { active: true } as MediaStream, stop });
    });
    await waitFor(() => expect(stop).toHaveBeenCalledOnce());
    expect(screen.queryByRole('button', { name: 'Finish recording' })).not.toBeInTheDocument();
  });
});

describe('configured transcription', () => {
  it('sends the complete recording to the server transcription route', async () => {
    const blob = new Blob(['recording']);
    vi.mocked(recordMicrophone).mockResolvedValue({
      stream: { active: true } as MediaStream,
      stop: vi.fn().mockResolvedValue({ blob, duration: 12, pauseCount: 1, silenceSeconds: 2 }),
    });
    vi.spyOn(api, 'transcribe').mockResolvedValue({
      text: 'Transcribed by selected ASR',
      provider: 'openai-compatible',
    });
    render(<Interview id="s1" navigate={vi.fn()} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Record answer' }));
    await user.click(await screen.findByRole('button', { name: 'Finish recording' }));
    await waitFor(() =>
      expect(screen.getByLabelText('Your answer')).toHaveValue('Transcribed by selected ASR'),
    );
    expect(api.transcribe).toHaveBeenCalledWith(blob, 'en-HK', expect.any(AbortSignal));
  });

  it('aborts transcription on pause and ignores its late result', async () => {
    vi.mocked(recordMicrophone).mockResolvedValue({
      stream: { active: true } as MediaStream,
      stop: vi
        .fn()
        .mockResolvedValue({ blob: new Blob(), duration: 1, pauseCount: 0, silenceSeconds: 0 }),
    });
    let resolve!: (value: { text: string; provider: string }) => void;
    const transcribe = vi.spyOn(api, 'transcribe').mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    render(<Interview id="s1" navigate={vi.fn()} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Record answer' }));
    await user.click(await screen.findByRole('button', { name: 'Finish recording' }));
    await waitFor(() => expect(transcribe).toHaveBeenCalledOnce());
    await user.click(screen.getByRole('button', { name: /^Pause$/ }));
    expect(transcribe.mock.calls[0][2]?.aborted).toBe(true);
    await user.type(screen.getByLabelText('Your answer'), 'My new typed draft');
    await act(async () => {
      resolve({ text: 'Stale recognition', provider: 'openai-compatible' });
    });
    expect(screen.getByLabelText('Your answer')).toHaveValue('My new typed draft');
  });
  it('reads a question only after the manual action and stops it on pause', async () => {
    const stop = vi.fn();
    vi.mocked(playQuestion).mockReturnValue(stop);
    render(<Interview id="s1" navigate={vi.fn()} />);
    expect(playQuestion).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Read question' }));
    expect(playQuestion).toHaveBeenCalledWith(
      'Tell me about a project.',
      'en-HK',
      expect.objectContaining({ onEnd: expect.any(Function) }),
    );
    await userEvent.click(screen.getByRole('button', { name: /^Pause$/ }));
    expect(stop).toHaveBeenCalled();
  });
});
