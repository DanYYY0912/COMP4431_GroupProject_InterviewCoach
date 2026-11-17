import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { api } from './lib/api';

beforeEach(() => {
  window.location.hash = '';
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  vi.spyOn(api, 'health').mockResolvedValue({
    status: 'ok',
    database: 'ready',
    llm: 'demo',
    speech: 'Whisper',
    retrieval: 'lexical',
    provider: 'demo',
  });
  vi.spyOn(api, 'sessions').mockResolvedValue([]);
});
afterEach(() => vi.restoreAllMocks());
describe('simplified navigation', () => {
  it('opens interview setup at the root without the overview, promotional panels or consent controls', async () => {
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Practice interview' })).toBeInTheDocument();
    const nav = within(screen.getByRole('navigation', { name: 'Main navigation' }));
    expect(nav.getByRole('link', { name: 'Practice interview' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(nav.getAllByRole('link')).toHaveLength(3);
    expect(nav.queryByRole('link', { name: 'Overview' })).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(
      /Azure|FIND YOUR VOICE|A space to grow|LOCAL-FIRST PRACTICE|COMP4431|Made for your next opportunity|Set the scene/,
    );
  });
  it('opens plain history through its own navigation tab', async () => {
    render(<App />);
    await userEvent.click(
      within(screen.getByRole('navigation')).getByRole('link', { name: 'History' }),
    );
    expect(await screen.findByRole('heading', { name: 'History' })).toBeInTheDocument();
    expect(await screen.findByText('No saved sessions.')).toBeInTheDocument();
    expect(window.location.hash).toBe('#/history');
    expect(
      screen.queryByText(/A little practice|A lot more|Your next chapter/),
    ).not.toBeInTheDocument();
  });
});
