import { act, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
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
vi.mock('../components/Interviewer3D', () => ({
  Interviewer3D: ({
    interviewer,
    speaking,
    speechCue,
  }: {
    interviewer: string;
    speaking: boolean;
    speechCue: number;
  }) => (
    <div
      data-testid="interviewer"
      data-interviewer={interviewer}
      data-speaking={String(speaking)}
      data-cue={speechCue}
    >
      Jamie
    </div>
  ),
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
  interviewer: 'jamie',
};
const control = vi.fn().mockResolvedValue(undefined);
let liveState: ReturnType<typeof useLiveSession>;
afterEach(() => vi.restoreAllMocks());
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(playQuestion).mockReset().mockReturnValue(vi.fn());
  liveState = {
    session,
    busy: false,
    error: '',
    setError: vi.fn(),
    state: 'ready',
    streamText: '',
    answer: vi.fn(),
    control,
  };
  vi.mocked(useLiveSession).mockImplementation(() => liveState);
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
  it('automatically reads the first question and supports manual replay and pause', async () => {
    const stop = vi.fn();
    vi.mocked(playQuestion).mockReturnValue(stop);
    render(<Interview id="s1" navigate={vi.fn()} />);
    await waitFor(() => expect(playQuestion).toHaveBeenCalledOnce());
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

describe('automatic questions and speech animation', () => {
  it('starts automatic playback once after StrictMode setup and cleanup', async () => {
    const stop = vi.fn();
    vi.mocked(playQuestion).mockReturnValue(stop);
    render(
      <StrictMode>
        <Interview id="s1" navigate={vi.fn()} />
      </StrictMode>,
    );
    await waitFor(() => expect(playQuestion).toHaveBeenCalledOnce());
    expect(stop).not.toHaveBeenCalled();
  });

  it('reads each turn once without replaying on pause, resume or a normal rerender', async () => {
    const view = render(<Interview id="s1" navigate={vi.fn()} />);
    await waitFor(() => expect(playQuestion).toHaveBeenCalledOnce());
    for (const state of ['paused', 'listening', 'listening'] as const) {
      liveState = { ...liveState, session: { ...session, state } };
      view.rerender(<Interview id="s1" navigate={vi.fn()} />);
    }
    await waitFor(() => expect(playQuestion).toHaveBeenCalledOnce());
    liveState = {
      ...liveState,
      session: {
        ...session,
        current_question: 2,
        turns: [
          ...session.turns,
          {
            ...session.turns[0],
            id: 't2',
            question: { ...session.turns[0].question, interviewer_text: 'What happened next?' },
          },
        ],
      },
    };
    view.rerender(<Interview id="s1" navigate={vi.fn()} />);
    await waitFor(() => expect(playQuestion).toHaveBeenCalledTimes(2));
    expect(vi.mocked(playQuestion).mock.lastCall?.[0]).toBe('What happened next?');
    liveState = { ...liveState, session };
    view.rerender(<Interview id="s1" navigate={vi.fn()} />);
    await waitFor(() => expect(playQuestion).toHaveBeenCalledTimes(2));
  });

  it('does not animate before actual speech and resets the saved Jamie face on completion', async () => {
    render(<Interview id="s1" navigate={vi.fn()} />);
    const face = screen.getByTestId('interviewer');
    expect(face).toHaveAttribute('data-interviewer', 'jamie');
    expect(face).toHaveAttribute('data-speaking', 'false');
    await waitFor(() => expect(playQuestion).toHaveBeenCalledOnce());
    const callbacks = vi.mocked(playQuestion).mock.calls[0][2];
    act(() => callbacks.onStart());
    expect(face).toHaveAttribute('data-speaking', 'true');
    expect(face).toHaveAttribute('data-cue', '0.65');
    act(() => callbacks.onViseme?.(0.3));
    expect(face).toHaveAttribute('data-cue', '0.3');
    act(() => callbacks.onEnd());
    expect(face).toHaveAttribute('data-speaking', 'false');
    expect(face).toHaveAttribute('data-cue', '0');
  });

  it('can disable automatic reading without losing manual playback', async () => {
    const stop = vi.fn();
    vi.mocked(playQuestion).mockReturnValue(stop);
    const view = render(<Interview id="s1" navigate={vi.fn()} />);
    const checkbox = screen.getByRole('checkbox', { name: 'Read questions automatically' });
    expect(checkbox).toBeChecked();
    await userEvent.click(checkbox);
    expect(stop).toHaveBeenCalled();
    liveState = {
      ...liveState,
      session: { ...session, turns: [{ ...session.turns[0], id: 't2' }] },
    };
    view.rerender(<Interview id="s1" navigate={vi.fn()} />);
    await waitFor(() => expect(playQuestion).toHaveBeenCalledOnce());
    await userEvent.click(screen.getByRole('button', { name: 'Read question' }));
    await waitFor(() => expect(playQuestion).toHaveBeenCalledTimes(2));
    await userEvent.click(checkbox);
    await waitFor(() => expect(playQuestion).toHaveBeenCalledTimes(2));
  });

  it('waits until generation finishes and stops pending playback on unmount', async () => {
    liveState = { ...liveState, busy: true };
    const stop = vi.fn();
    vi.mocked(playQuestion).mockReturnValue(stop);
    const view = render(<Interview id="s1" navigate={vi.fn()} />);
    expect(playQuestion).not.toHaveBeenCalled();
    liveState = { ...liveState, busy: false };
    view.rerender(<Interview id="s1" navigate={vi.fn()} />);
    await waitFor(() => expect(playQuestion).toHaveBeenCalledOnce());
    view.unmount();
    expect(stop).toHaveBeenCalledOnce();
  });

  it('clears speech on pause and ignores late animation callbacks from the old question', async () => {
    const stop = vi.fn();
    vi.mocked(playQuestion).mockReturnValue(stop);
    const view = render(<Interview id="s1" navigate={vi.fn()} />);
    await waitFor(() => expect(playQuestion).toHaveBeenCalledOnce());
    const callbacks = vi.mocked(playQuestion).mock.calls[0][2];
    act(() => callbacks.onStart());
    liveState = { ...liveState, session: { ...session, state: 'paused' } };
    view.rerender(<Interview id="s1" navigate={vi.fn()} />);
    expect(stop).toHaveBeenCalledOnce();
    act(() => {
      callbacks.onStart();
      callbacks.onViseme?.(1);
    });
    expect(screen.getByTestId('interviewer')).toHaveAttribute('data-speaking', 'false');
    expect(screen.getByTestId('interviewer')).toHaveAttribute('data-cue', '0');
  });

  it('stops playback when the session completes before opening the report', async () => {
    const stop = vi.fn();
    const navigate = vi.fn();
    vi.mocked(playQuestion).mockReturnValue(stop);
    const view = render(<Interview id="s1" navigate={navigate} />);
    await waitFor(() => expect(playQuestion).toHaveBeenCalledOnce());
    act(() => vi.mocked(playQuestion).mock.calls[0][2].onStart());
    liveState = { ...liveState, session: { ...session, state: 'completed' } };
    view.rerender(<Interview id="s1" navigate={navigate} />);
    expect(stop).toHaveBeenCalledOnce();
    expect(navigate).toHaveBeenCalledWith('/report/s1');
    expect(screen.getByTestId('interviewer')).toHaveAttribute('data-speaking', 'false');
    expect(playQuestion).toHaveBeenCalledOnce();
  });

  it('keeps automatic reading silent while recording or transcribing', async () => {
    vi.mocked(recordMicrophone).mockResolvedValue({
      stream: { active: true } as MediaStream,
      stop: vi
        .fn()
        .mockResolvedValue({ blob: new Blob(), duration: 5, pauseCount: 0, silenceSeconds: 0 }),
    });
    let resolve!: (value: { text: string; provider: string }) => void;
    vi.spyOn(api, 'transcribe').mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    const view = render(<Interview id="s1" navigate={vi.fn()} />);
    await waitFor(() => expect(playQuestion).toHaveBeenCalledOnce());
    await userEvent.click(screen.getByRole('button', { name: 'Record answer' }));
    liveState = {
      ...liveState,
      session: { ...session, turns: [{ ...session.turns[0], id: 't2' }] },
    };
    view.rerender(<Interview id="s1" navigate={vi.fn()} />);
    await act(async () => {});
    expect(playQuestion).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole('button', { name: 'Finish recording' }));
    await waitFor(() => expect(api.transcribe).toHaveBeenCalledOnce());
    expect(playQuestion).toHaveBeenCalledOnce();
    await act(async () => {
      resolve({ text: 'Answer', provider: 'openai-compatible' });
    });
    await waitFor(() => expect(playQuestion).toHaveBeenCalledTimes(2));
  });
});
