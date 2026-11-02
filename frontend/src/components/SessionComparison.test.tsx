import { render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../lib/api';
import { SessionComparison } from './SessionComparison';
import type { Report, Session } from '../lib/types';

const base = {
  job_profile_id: 'job',
  difficulty: 'standard',
  question_count: 3,
  state: 'completed',
  current_question: 3,
  turns: [],
  created_at: '2026-11-02T08:00:00Z',
  provider: 'demo',
};
const left = { ...base, id: 'left', role_title: 'Software engineer', language: 'en-HK' } as Session;
const right = { ...base, id: 'right', role_title: 'Data analyst', language: 'zh-HK' } as Session;
function report(id: string, evidence: string, resultPresent: boolean): Report {
  return {
    session_id: id,
    role_title: id,
    language: 'en-HK',
    summary: 'Practice reflection',
    star: [
      {
        element: 'Result',
        present: resultPresent,
        evidence,
        coaching: 'Make the outcome concrete.',
      },
    ],
    competencies: [
      { name: 'Testing', evidence, feedback: 'Explain how you checked the change.', citations: [] },
    ],
    strengths: [],
    prioritized_improvement: 'Describe what changed.',
    retry_exercise: 'Try a more specific example.',
    speech_metrics: {
      word_count: 25,
      duration_seconds: 60,
      words_per_minute: 25,
      filler_count: 0,
      pause_count: null,
      silence_seconds: null,
      answer_count: 1,
    },
    citations: [],
    limitations: ['Demo provider.'],
  };
}
afterEach(() => vi.restoreAllMocks());
describe('session comparison', () => {
  it('keeps each session’s role, language and report evidence distinct without a quality score', async () => {
    vi.spyOn(api, 'report').mockImplementation(async (id) =>
      id === 'left'
        ? report(id, 'Latency fell by 30%.', true)
        : report(id, 'I wrote tests.', false),
    );
    render(<SessionComparison left={left} right={right} onClear={vi.fn()} />);
    const first = await screen.findByRole('article', { name: 'First session: Software engineer' });
    const second = screen.getByRole('article', { name: 'Second session: Data analyst' });
    expect(within(first).getByText('English')).toBeInTheDocument();
    expect(within(second).getByText('廣東話')).toBeInTheDocument();
    expect(within(first).getAllByText('Latency fell by 30%.')).toHaveLength(2);
    expect(within(second).getAllByText('I wrote tests.')).toHaveLength(2);
    expect(within(first).getByText('Evidence found')).toBeInTheDocument();
    expect(within(second).getByText('Room to develop')).toBeInTheDocument();
    expect(screen.queryByText(/quality score|overall score/i)).not.toBeInTheDocument();
  });
});
