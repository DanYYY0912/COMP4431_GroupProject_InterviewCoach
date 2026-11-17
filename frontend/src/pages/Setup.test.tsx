import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Setup } from './Setup';
import { api } from '../lib/api';
import type { Profile, Session } from '../lib/types';

beforeEach(() => {
  localStorage.clear();
  vi.spyOn(api, 'health').mockResolvedValue({
    status: 'ok',
    database: 'ready',
    llm: 'demo',
    speech: 'unavailable',
    retrieval: 'lexical',
    provider: 'demo',
  });
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});
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
    expect(create).toHaveBeenCalledWith('job-1', 'en-HK', 'standard', 3, 'jamie');
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}
const profile: Profile = {
  id: 'job-1',
  title: 'Developer',
  competencies: [],
  warnings: [],
  sources: [],
};
function submitSample() {
  fireEvent.click(screen.getByRole('button', { name: 'Try a sample role' }));
  fireEvent.submit(screen.getByRole('button', { name: 'Start my interview' }).closest('form')!);
}

describe('interviewer selection before starting', () => {
  it('remembers a valid preference, updates the summary and saves the selection with the session', async () => {
    localStorage.setItem('voxprep.interviewer', 'jamie');
    vi.spyOn(api, 'profile').mockResolvedValue(profile);
    const create = vi.spyOn(api, 'create').mockResolvedValue({ id: 'chosen-face' } as Session);
    const navigate = vi.fn();
    render(<Setup navigate={navigate} />);
    expect(screen.getByRole('radio', { name: 'Jamie' })).toBeChecked();
    expect(
      within(screen.getByRole('complementary', { name: 'Configuration status' })).getByText(
        'Jamie',
      ),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole('radio', { name: 'Jamie' }));
    expect(localStorage.getItem('voxprep.interviewer')).toBe('jamie');
    submitSample();
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/interview/chosen-face'));
    expect(create).toHaveBeenCalledWith('job-1', 'en-HK', 'standard', 5, 'jamie');
  });
  it('ignores invalid stored IDs and still allows selection if browser storage is unavailable', async () => {
    localStorage.setItem('voxprep.interviewer', 'alex');
    const first = render(<Setup navigate={vi.fn()} />);
    expect(screen.getByRole('radio', { name: 'Jamie' })).toBeChecked();
    expect(screen.getAllByRole('radio', { name: /Alex|Jamie|Sam/ })).toHaveLength(1);
    first.unmount();
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('Unavailable');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('Unavailable');
    });
    vi.spyOn(api, 'profile').mockResolvedValue(profile);
    const create = vi
      .spyOn(api, 'create')
      .mockResolvedValue({ id: 'storage-unavailable' } as Session);
    render(<Setup navigate={vi.fn()} />);
    expect(screen.getByRole('radio', { name: 'Jamie' })).toBeChecked();
    submitSample();
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith('job-1', 'en-HK', 'standard', 5, 'jamie'),
    );
  });
});

describe('startup progress', () => {
  it('tracks completed API stages, remains indeterminate and prevents duplicate submission', async () => {
    const profileRequest = deferred<Profile>();
    const sessionRequest = deferred<Session>();
    const read = vi.spyOn(api, 'profile').mockReturnValue(profileRequest.promise);
    const create = vi.spyOn(api, 'create').mockReturnValue(sessionRequest.promise);
    const navigate = vi.fn();
    render(<Setup navigate={navigate} />);
    fireEvent.click(screen.getByRole('button', { name: 'Try a sample role' }));
    const form = screen.getByLabelText('Job description').closest('form')!;
    act(() => {
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    });
    const bar = screen.getByRole('progressbar', { name: 'Interview preparation' });
    expect(bar).not.toHaveAttribute('aria-valuenow');
    expect(bar).toHaveAttribute('aria-valuetext', 'Reading and indexing the job description');
    expect(screen.getByLabelText('Job description')).toBeDisabled();
    expect(screen.getByRole('radio', { name: 'Jamie' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Preparing your interview…' })).toBeDisabled();
    fireEvent.submit(screen.getByLabelText('Job description').closest('form')!);
    expect(read).toHaveBeenCalledOnce();
    expect(create).not.toHaveBeenCalled();
    await act(async () => {
      profileRequest.resolve(profile);
    });
    expect(bar).toHaveAttribute('aria-valuetext', 'Preparing the first question');
    expect(
      screen.getByText('Reading and indexing the job description').closest('li'),
    ).toHaveTextContent('Done');
    expect(create).toHaveBeenCalledOnce();
    fireEvent.submit(screen.getByLabelText('Job description').closest('form')!);
    expect(create).toHaveBeenCalledOnce();
    await act(async () => {
      sessionRequest.resolve({ id: 'new-session' } as Session);
    });
    expect(bar).toHaveAttribute('aria-valuetext', 'Opening interview');
    expect(navigate).toHaveBeenCalledOnce();
    expect(navigate).toHaveBeenCalledWith('/interview/new-session');
  });
  it('identifies an upload while the selected document is being processed', () => {
    const read = vi.spyOn(api, 'profile').mockReturnValue(new Promise(() => {}));
    render(<Setup navigate={vi.fn()} />);
    const file = new File(['Developer role and responsibilities'], 'role.txt');
    fireEvent.change(screen.getByLabelText('Upload a job description'), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Start my interview' }));
    expect(screen.getByRole('progressbar')).toHaveAttribute(
      'aria-valuetext',
      'Uploading and indexing the job description',
    );
    expect(read).toHaveBeenCalledWith('', file);
  });
  it('shows elapsed time and a useful slow-request message without inventing a percentage', async () => {
    vi.useFakeTimers();
    vi.spyOn(api, 'profile').mockReturnValue(new Promise(() => {}));
    render(<Setup navigate={vi.fn()} />);
    submitSample();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(16000);
    });
    expect(screen.getByText('Elapsed 0:16')).toBeInTheDocument();
    expect(screen.getByText(/retrieval services are still processing/)).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow');
    expect(screen.queryByText(/100%/)).not.toBeInTheDocument();
  });
  it('stops progress after a failed first-question request and retains the form for a deliberate retry', async () => {
    vi.spyOn(api, 'profile').mockResolvedValue(profile);
    const sessionRequest = deferred<Session>();
    const create = vi.spyOn(api, 'create').mockReturnValue(sessionRequest.promise);
    render(<Setup navigate={vi.fn()} />);
    await userEvent.click(screen.getByRole('radio', { name: 'Jamie' }));
    submitSample();
    await waitFor(() => expect(create).toHaveBeenCalledOnce());
    await act(async () => {
      sessionRequest.reject(new Error('The model service is unavailable.'));
    });
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('model service is unavailable');
    expect(screen.getByRole('radio', { name: 'Jamie' })).toBeChecked();
    expect((screen.getByLabelText('Job description') as HTMLTextAreaElement).value).toContain(
      'Graduate Software Engineer',
    );
    expect(screen.getByRole('button', { name: 'Start my interview' })).toBeEnabled();
    expect(create).toHaveBeenCalledOnce();
  });
  it('finishes the requested session without late navigation when setup was left during indexing', async () => {
    const pending = deferred<Profile>();
    vi.spyOn(api, 'profile').mockReturnValue(pending.promise);
    const create = vi.spyOn(api, 'create').mockResolvedValue({ id: 'saved-in-history' } as Session);
    const navigate = vi.fn();
    const page = render(<Setup navigate={navigate} />);
    submitSample();
    page.unmount();
    await act(async () => {
      pending.resolve(profile);
    });
    expect(create).toHaveBeenCalledOnce();
    expect(navigate).not.toHaveBeenCalled();
  });
  it('does not navigate late if session creation finishes after leaving setup', async () => {
    vi.spyOn(api, 'profile').mockResolvedValue(profile);
    const pending = deferred<Session>();
    const create = vi.spyOn(api, 'create').mockReturnValue(pending.promise);
    const navigate = vi.fn();
    const page = render(<Setup navigate={navigate} />);
    submitSample();
    await waitFor(() => expect(create).toHaveBeenCalledOnce());
    page.unmount();
    await act(async () => {
      pending.resolve({ id: 'saved-in-history' } as Session);
    });
    expect(navigate).not.toHaveBeenCalled();
    expect(create).toHaveBeenCalledOnce();
  });
});
