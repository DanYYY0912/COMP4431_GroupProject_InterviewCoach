import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';
import { loadSessionExport } from './sessionExport';
import type { Report, Session } from './types';

const session: Session = {
  id: 'session-1',
  job_profile_id: 'job-1',
  role_title: 'Developer',
  language: 'zh-HK',
  difficulty: 'standard',
  question_count: 3,
  state: 'completed',
  current_question: 1,
  created_at: '2026-11-02T08:00:00Z',
  provider: 'demo',
  turns: [
    {
      id: 'turn-1',
      created_at: '2026-11-02T08:00:00Z',
      question: {
        interviewer_text: '講下一次你改善系統嘅經驗。',
        question_type: 'opening',
        targeted_competencies: ['Testing'],
        adaptive_follow_up_reason: null,
        citations: [{ chunk_id: 'c1', source: 'Job description', text: 'Write automated tests.' }],
      },
      answer: {
        transcript: '我加入自動測試，結果錯誤減少。',
        language: 'zh-HK',
        elapsed_seconds: 32,
        corrected: true,
        turn_id: 'turn-1',
      },
    },
  ],
};
const report = { session_id: 'session-1', summary: 'Reflect on your evidence.' } as Report;
afterEach(() => vi.restoreAllMocks());
describe('full session export', () => {
  it('includes saved questions, corrected transcript, source citations, report and metadata', async () => {
    vi.spyOn(api, 'session').mockResolvedValue(session);
    vi.spyOn(api, 'report').mockResolvedValue(report);
    const content = await loadSessionExport('session-1');
    expect(content.format).toBe('voxprep.session');
    expect(content.version).toBe(1);
    expect(content.session.turns[0].answer?.transcript).toBe('我加入自動測試，結果錯誤減少。');
    expect(content.session.turns[0].answer?.corrected).toBe(true);
    expect(content.session.turns[0].question.citations[0].chunk_id).toBe('c1');
    expect(content.session.provider).toBe('demo');
    expect(content.report).toEqual(report);
    expect(Number.isFinite(Date.parse(content.exported_at))).toBe(true);
  });
  it('exports an incomplete saved session without inventing a debrief', async () => {
    vi.spyOn(api, 'session').mockResolvedValue({ ...session, state: 'paused' });
    const getReport = vi.spyOn(api, 'report');
    const content = await loadSessionExport('session-1');
    expect(content.report).toBeNull();
    expect(getReport).not.toHaveBeenCalled();
    expect(content.session.turns).toEqual(session.turns);
  });
  it('rejects a mismatched report instead of combining different sessions', async () => {
    vi.spyOn(api, 'session').mockResolvedValue(session);
    vi.spyOn(api, 'report').mockResolvedValue({ ...report, session_id: 'another-session' });
    await expect(loadSessionExport('session-1')).rejects.toThrow('does not match');
  });
});
