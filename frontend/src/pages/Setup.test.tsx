import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Setup } from './Setup';
import { api } from '../lib/api';
import type { Session } from '../lib/types';

beforeEach(() => {
  vi.spyOn(api, 'health').mockResolvedValue({
    status: 'ok',
    database: 'ready',
    llm: 'demo',
    speech: 'unavailable',
    retrieval: 'lexical',
    provider: 'demo',
  });
});
afterEach(() => vi.restoreAllMocks());
describe('interview setup', () => {
  it('requires local transcript consent and does not enable cloud voice implicitly', async () => {
    const user = userEvent.setup();
    const navigate = vi.fn();
    const speechConsent = vi.fn();
    vi.spyOn(api, 'profile').mockResolvedValue({
      id: 'job-1',
      title: 'Software Engineer',
      competencies: ['Testing'],
      warnings: [],
      sources: [],
    });
    const create = vi.spyOn(api, 'create').mockResolvedValue({ id: 'session-1' } as Session);
    render(<Setup navigate={navigate} onSpeechConsent={speechConsent} />);
    await user.click(screen.getByRole('button', { name: 'Try a sample role' }));
    expect(screen.getByRole('button', { name: 'Start my interview' })).toBeDisabled();
    await user.click(screen.getByRole('checkbox', { name: /Save this session/ }));
    await user.selectOptions(screen.getByLabelText('Number of questions'), '3');
    await user.click(screen.getByRole('button', { name: 'Start my interview' }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/interview/session-1'));
    expect(create).toHaveBeenCalledWith('job-1', 'en-HK', 'standard', 3);
    expect(speechConsent).toHaveBeenCalledWith(false);
  });
  it('rejects an oversized attachment before sending it to the API', async () => {
    render(<Setup navigate={vi.fn()} onSpeechConsent={vi.fn()} />);
    const file = new File(['content'], 'large.pdf', { type: 'application/pdf' });
    Object.defineProperty(file, 'size', { value: 6 * 1024 * 1024 });
    fireEvent.change(screen.getByLabelText('Upload a job description'), {
      target: { files: [file] },
    });
    expect(await screen.findByRole('alert')).toHaveTextContent('no larger than 5 MB');
    expect(screen.queryByText('large.pdf')).not.toBeInTheDocument();
  });
  it('preserves the form when ingestion fails', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'profile').mockRejectedValue(new Error('This document has no extractable text.'));
    render(<Setup navigate={vi.fn()} onSpeechConsent={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: 'Try a sample role' }));
    await user.click(screen.getByRole('checkbox', { name: /Save this session/ }));
    await user.click(screen.getByRole('button', { name: 'Start my interview' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('no extractable text');
    expect((screen.getByLabelText('Job description') as HTMLTextAreaElement).value).toContain(
      'Graduate Software Engineer',
    );
    expect(screen.getByRole('button', { name: 'Start my interview' })).toBeEnabled();
  });
});
