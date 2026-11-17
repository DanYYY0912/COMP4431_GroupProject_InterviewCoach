import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { InterviewerPortrait } from './InterviewerPortrait';

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe('interviewer appearance', () => {
  it('defaults to Alex and exposes three labelled face choices', () => {
    render(<InterviewerPortrait />);
    expect(screen.getByRole('group', { name: 'Interviewer appearance' })).toBeInTheDocument();
    expect(screen.getAllByRole('radio')).toHaveLength(3);
    expect(screen.getByRole('radio', { name: 'Alex' })).toBeChecked();
    expect(screen.getByRole('img', { name: 'Alex, interviewer portrait' })).toHaveAttribute(
      'src',
      '/interviewers/alex.png',
    );
  });
  it('saves a selected face and restores it when the page mounts again', async () => {
    const first = render(<InterviewerPortrait />);
    await userEvent.click(screen.getByRole('radio', { name: 'Sam' }));
    expect(localStorage.getItem('voxprep.interviewer')).toBe('sam');
    expect(screen.getByRole('img', { name: 'Sam, interviewer portrait' })).toBeInTheDocument();
    first.unmount();
    render(<InterviewerPortrait />);
    expect(screen.getByRole('radio', { name: 'Sam' })).toBeChecked();
    expect(screen.getByRole('img', { name: 'Sam, interviewer portrait' })).toBeInTheDocument();
  });
  it('ignores invalid stored values instead of turning them into image URLs', () => {
    localStorage.setItem('voxprep.interviewer', 'https://untrusted.example/face.png');
    render(<InterviewerPortrait />);
    expect(screen.getByRole('radio', { name: 'Alex' })).toBeChecked();
    expect(screen.getByRole('img', { name: 'Alex, interviewer portrait' })).toHaveAttribute(
      'src',
      '/interviewers/alex.png',
    );
  });
  it('keeps selection usable when browser storage cannot be read or written', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('Storage unavailable');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('Storage unavailable');
    });
    render(<InterviewerPortrait />);
    await userEvent.click(screen.getByRole('radio', { name: 'Jamie' }));
    expect(screen.getByRole('radio', { name: 'Jamie' })).toBeChecked();
    expect(screen.getByRole('img', { name: 'Jamie, interviewer portrait' })).toBeInTheDocument();
  });
  it('hides and restores the selected portrait without replacing it with an illustration', async () => {
    render(<InterviewerPortrait />);
    await userEvent.click(screen.getByRole('radio', { name: 'Jamie' }));
    await userEvent.click(screen.getByRole('button', { name: 'Hide interviewer portrait' }));
    expect(
      screen.queryByRole('img', { name: 'Jamie, interviewer portrait' }),
    ).not.toBeInTheDocument();
    expect(screen.getByText('Portrait hidden')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Jamie' })).toBeChecked();
    await userEvent.click(screen.getByRole('button', { name: 'Show interviewer portrait' }));
    expect(screen.getByRole('img', { name: 'Jamie, interviewer portrait' })).toBeInTheDocument();
  });
  it('falls back to quiet text if a photograph fails and permits another selection', async () => {
    render(<InterviewerPortrait />);
    fireEvent.error(screen.getByRole('img', { name: 'Alex, interviewer portrait' }));
    expect(screen.getByRole('status')).toHaveTextContent('Portrait unavailable');
    await userEvent.click(screen.getByRole('radio', { name: 'Sam' }));
    expect(screen.getByRole('img', { name: 'Sam, interviewer portrait' })).toBeInTheDocument();
    expect(screen.queryByText('Portrait unavailable')).not.toBeInTheDocument();
  });
});
