import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Interviewer3D } from './Interviewer3D';
import { createPortraitScene } from '../lib/portraitScene';

vi.mock('../lib/portraitScene', () => ({ createPortraitScene: vi.fn() }));
const base = { interviewer: 'jamie' as const, state: 'ready', speaking: false, speechCue: 0 };
beforeEach(() => {
  vi.mocked(createPortraitScene).mockReset();
});
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

describe('3D interviewer lifecycle', () => {
  it('updates motion without rebuilding the scene and disposes it when hidden', async () => {
    const dispose = vi.fn();
    vi.mocked(createPortraitScene).mockResolvedValue(dispose);
    const page = render(<Interviewer3D {...base} />);
    await waitFor(() => expect(createPortraitScene).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.queryByText('Loading interviewer…')).not.toBeInTheDocument());
    page.rerender(<Interviewer3D {...base} speaking speechCue={0.8} state="speaking" />);
    expect(createPortraitScene).toHaveBeenCalledOnce();
    expect(vi.mocked(createPortraitScene).mock.calls[0][3]()).toMatchObject({
      speaking: true,
      speechCue: 0.8,
      state: 'speaking',
    });
    await userEvent.click(screen.getByRole('button', { name: 'Hide interviewer' }));
    expect(vi.mocked(createPortraitScene).mock.calls[0][4].aborted).toBe(true);
    expect(dispose).toHaveBeenCalledOnce();
    expect(screen.getByText('Interviewer hidden')).toBeInTheDocument();
  });
  it('cleans up a scene that finishes initializing after it was hidden', async () => {
    const pending = deferred<() => void>();
    const dispose = vi.fn();
    vi.mocked(createPortraitScene).mockReturnValue(pending.promise);
    render(<Interviewer3D {...base} />);
    await waitFor(() => expect(createPortraitScene).toHaveBeenCalledOnce());
    await userEvent.click(screen.getByRole('button', { name: 'Hide interviewer' }));
    await act(async () => {
      pending.resolve(dispose);
    });
    expect(dispose).toHaveBeenCalledOnce();
    expect(screen.getByText('Interviewer hidden')).toBeInTheDocument();
    expect(screen.queryByText('Loading interviewer…')).not.toBeInTheDocument();
  });
  it('aborts initialization and disposes a late scene after unmount', async () => {
    const pending = deferred<() => void>();
    const dispose = vi.fn();
    vi.mocked(createPortraitScene).mockReturnValue(pending.promise);
    const page = render(<Interviewer3D {...base} />);
    await waitFor(() => expect(createPortraitScene).toHaveBeenCalledOnce());
    page.unmount();
    expect(vi.mocked(createPortraitScene).mock.calls[0][4].aborted).toBe(true);
    await act(async () => {
      pending.resolve(dispose);
    });
    expect(dispose).toHaveBeenCalledOnce();
  });
  it('keeps a portrait fallback when initialization fails', async () => {
    vi.mocked(createPortraitScene).mockRejectedValue(new Error('WebGL unavailable'));
    render(<Interviewer3D {...base} />);
    await screen.findByText(/3D view unavailable/);
    expect(screen.getByRole('img', { name: 'Jamie, interviewer portrait' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Hide interviewer' })).toBeEnabled();
  });
  it('does not replace an early context-loss fallback with ready state', async () => {
    const dispose = vi.fn();
    vi.mocked(createPortraitScene).mockImplementation(
      async (_host, _src, _mesh, _motion, _signal, fail) => {
        fail();
        return dispose;
      },
    );
    render(<Interviewer3D {...base} />);
    await waitFor(() => expect(dispose).toHaveBeenCalledOnce());
    expect(screen.getByText(/3D view unavailable/)).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Jamie, interviewer portrait' })).toBeInTheDocument();
  });
});
