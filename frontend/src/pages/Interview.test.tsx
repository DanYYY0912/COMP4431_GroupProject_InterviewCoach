import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Interview } from './Interview';
import { useLiveSession } from '../lib/useLiveSession';
import { azureRecognizer, recordMicrophone } from '../lib/audio';
import type { Session } from '../lib/types';

vi.mock('../lib/useLiveSession', () => ({ useLiveSession: vi.fn() }));
vi.mock('../lib/audio', () => ({
  recordMicrophone: vi.fn(),
  azureRecognizer: vi.fn(),
  playQuestion: vi.fn(() => vi.fn()),
}));
vi.mock('../components/Avatar', () => ({ default: () => <div>Coach portrait</div> }));

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
beforeEach(() => {
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
    render(
      <Interview id="s1" navigate={vi.fn()} speechConsent={false} onSpeechConsent={vi.fn()} />,
    );
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
    render(<Interview id="s1" navigate={vi.fn()} speechConsent={true} onSpeechConsent={vi.fn()} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Record answer' }));
    await user.click(screen.getByRole('button', { name: /^Pause$/ }));
    await act(async () => {
      resolveCapture({ stream: { active: true } as MediaStream, stop });
    });
    await waitFor(() => expect(stop).toHaveBeenCalledOnce());
    expect(azureRecognizer).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'Finish recording' })).not.toBeInTheDocument();
  });
});
