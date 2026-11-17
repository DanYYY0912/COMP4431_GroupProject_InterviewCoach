import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
  it('enables start from valid left-side fields without a consent or service-configuration gate', async () => {
    const user = userEvent.setup();
    const navigate = vi.fn();
    vi.spyOn(api, 'profile').mockResolvedValue({
      id: 'job-1',
      title: 'Software Engineer',
      competencies: ['Testing'],
      warnings: [],
      sources: [],
    });
    const create = vi.spyOn(api, 'create').mockResolvedValue({ id: 'session-1' } as Session);
    render(<Setup navigate={navigate} />);
    expect(screen.getByRole('button', { name: 'Start my interview' })).toBeDisabled();
    await user.type(screen.getByLabelText('Job description'), 'Short role');
    expect(screen.getByRole('button', { name: 'Start my interview' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Try a sample role' }));
    expect(screen.getByRole('button', { name: 'Start my interview' })).toBeEnabled();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Number of questions'), '3');
    await user.click(screen.getByRole('button', { name: 'Start my interview' }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/interview/session-1'));
    expect(create).toHaveBeenCalledWith('job-1', 'en-HK', 'standard', 3);
  });
  it('keeps the right column read-only while reflecting the selected configuration', async () => {
    render(<Setup navigate={vi.fn()} />);
    const user = userEvent.setup();
    const status = within(screen.getByRole('complementary', { name: 'Configuration status' }));
    expect(status.getByText('Missing')).toBeInTheDocument();
    expect(status.queryAllByRole('button')).toHaveLength(0);
    expect(status.queryAllByRole('checkbox')).toHaveLength(0);
    expect(status.queryAllByRole('combobox')).toHaveLength(0);
    await user.click(screen.getByRole('radio', { name: '廣東話' }));
    await user.selectOptions(screen.getByLabelText('Difficulty'), 'stretch');
    await user.selectOptions(screen.getByLabelText('Number of questions'), '8');
    expect(status.getByText('廣東話')).toBeInTheDocument();
    expect(status.getByText('Stretch')).toBeInTheDocument();
    expect(status.getByText('8')).toBeInTheDocument();
    expect(status.getByRole('link', { name: 'Inference settings' })).toHaveAttribute(
      'href',
      '#/settings',
    );
  });
  it('accepts a valid uploaded document and disables start again when removed', async () => {
    render(<Setup navigate={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Upload a job description'), {
      target: { files: [new File(['A job description'], 'role.txt')] },
    });
    expect(screen.getByRole('button', { name: 'Start my interview' })).toBeEnabled();
    expect(screen.getByLabelText('Job description')).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Remove selected file' }));
    expect(screen.getByRole('button', { name: 'Start my interview' })).toBeDisabled();
  });
  it('rejects an oversized attachment before sending it to the API', async () => {
    render(<Setup navigate={vi.fn()} />);
    const file = new File(['content'], 'large.pdf', { type: 'application/pdf' });
    Object.defineProperty(file, 'size', { value: 6 * 1024 * 1024 });
    fireEvent.change(screen.getByLabelText('Upload a job description'), {
      target: { files: [file] },
    });
    expect(await screen.findByRole('alert')).toHaveTextContent('no larger than 5 MB');
    expect(screen.getByRole('button', { name: 'Start my interview' })).toBeDisabled();
  });
  it('preserves the form when ingestion fails', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'profile').mockRejectedValue(new Error('This document has no extractable text.'));
    render(<Setup navigate={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: 'Try a sample role' }));
    await user.click(screen.getByRole('button', { name: 'Start my interview' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('no extractable text');
    expect((screen.getByLabelText('Job description') as HTMLTextAreaElement).value).toContain(
      'Graduate Software Engineer',
    );
    expect(screen.getByRole('button', { name: 'Start my interview' })).toBeEnabled();
  });
  it('reports unavailable readiness without making it an extra start requirement', async () => {
    vi.mocked(api.health).mockRejectedValue(new Error('Unavailable'));
    render(<Setup navigate={vi.fn()} />);
    await screen.findByText(/Server status is unavailable/);
    await userEvent.click(screen.getByRole('button', { name: 'Try a sample role' }));
    expect(screen.getByRole('button', { name: 'Start my interview' })).toBeEnabled();
  });
});
