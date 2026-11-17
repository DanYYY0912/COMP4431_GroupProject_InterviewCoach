import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../lib/api';
import type { InferenceSettings as SavedSettings, InferenceSettingsUpdate } from '../lib/types';
import { InferenceSettings } from './InferenceSettings';

const saved: SavedSettings = {
  agent: { base_url: 'http://localhost:8001/v1', model: 'coach', api_key_set: true },
  asr: { base_url: '', model: '', api_key_set: false },
  embedding: { base_url: 'http://localhost:8002/v1', model: 'embed', api_key_set: true },
  reranker: { base_url: '', model: '', api_key_set: false },
};
function savedResponse(update: InferenceSettingsUpdate): SavedSettings {
  return Object.fromEntries(
    Object.entries(update).map(([id, entry]) => [
      id,
      {
        base_url: entry.base_url,
        model: entry.model,
        api_key_set:
          entry.api_key === null ? saved[id as keyof SavedSettings].api_key_set : !!entry.api_key,
      },
    ]),
  ) as SavedSettings;
}
beforeEach(() => {
  vi.spyOn(api, 'inferenceSettings').mockResolvedValue(saved);
  vi.spyOn(api, 'saveInferenceSettings').mockImplementation(async (update) =>
    savedResponse(update),
  );
});
afterEach(() => vi.restoreAllMocks());
async function open() {
  render(<InferenceSettings />);
  await screen.findByLabelText('Agent base URL');
  return userEvent.setup();
}

describe('inference settings', () => {
  it('keeps saved keys redacted and retains them when editing a model at the same URL', async () => {
    const user = await open();
    expect(screen.getByLabelText('Agent API key')).toHaveAttribute('type', 'password');
    expect(screen.getByLabelText('Agent API key')).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Save settings' })).toBeDisabled();
    await user.clear(screen.getByLabelText('Agent model'));
    await user.type(screen.getByLabelText('Agent model'), 'coach-new');
    await user.click(screen.getByRole('button', { name: 'Save settings' }));
    await screen.findByText('Settings saved. New requests use these settings immediately.');
    expect(api.saveInferenceSettings).toHaveBeenCalledWith({
      agent: { base_url: saved.agent.base_url, model: 'coach-new', api_key: null },
      asr: { base_url: '', model: '', api_key: null },
      embedding: { base_url: saved.embedding.base_url, model: 'embed', api_key: null },
      reranker: { base_url: '', model: '', api_key: null },
    });
    expect(screen.getByLabelText('Agent API key')).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Save settings' })).toBeDisabled();
  });

  it('clears the previous key when the URL changes and discovery uses that same safe payload', async () => {
    vi.spyOn(api, 'inferenceModels').mockResolvedValue({ models: ['other-coach'] });
    const user = await open();
    await user.clear(screen.getByLabelText('Agent base URL'));
    await user.type(screen.getByLabelText('Agent base URL'), 'https://inference.example/v1');
    expect(
      screen.getByText(/The base URL changed. The saved key will not be reused/),
    ).toBeInTheDocument();
    await user.click(
      within(screen.getByRole('group', { name: 'Agent' })).getByRole('button', {
        name: 'Load models',
      }),
    );
    await screen.findByText('1 model available. Choose one or enter a model name.');
    expect(api.inferenceModels).toHaveBeenCalledWith('agent', {
      base_url: 'https://inference.example/v1',
      api_key: '',
    });
    await user.click(screen.getByRole('button', { name: 'Save settings' }));
    await waitFor(() =>
      expect(api.saveInferenceSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          agent: { base_url: 'https://inference.example/v1', model: 'coach', api_key: '' },
        }),
      ),
    );
  });

  it('supports explicit key removal and clears a newly submitted key from form memory after saving', async () => {
    const user = await open();
    await user.click(screen.getByRole('button', { name: 'Clear Agent API key' }));
    expect(screen.getByText('The saved key will be cleared when you save.')).toBeInTheDocument();
    await user.type(screen.getByLabelText('Embedding API key'), 'test-new-key');
    await user.click(screen.getByRole('button', { name: 'Save settings' }));
    await screen.findByText('Settings saved. New requests use these settings immediately.');
    expect(api.saveInferenceSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        agent: { base_url: saved.agent.base_url, model: 'coach', api_key: '' },
        embedding: { base_url: saved.embedding.base_url, model: 'embed', api_key: 'test-new-key' },
      }),
    );
    expect(screen.getByLabelText('Embedding API key')).toHaveValue('');
  });

  it('discovers models with an unsaved key and keeps the chosen model editable', async () => {
    vi.spyOn(api, 'inferenceModels').mockResolvedValue({
      models: ['coach-b', 'coach-a', 'coach-a'],
    });
    const user = await open();
    await user.type(screen.getByLabelText('Agent API key'), 'test-discovery-key');
    await user.click(
      within(screen.getByRole('group', { name: 'Agent' })).getByRole('button', {
        name: 'Load models',
      }),
    );
    await screen.findByText('2 models available. Choose one or enter a model name.');
    expect(api.inferenceModels).toHaveBeenCalledWith('agent', {
      base_url: saved.agent.base_url,
      api_key: 'test-discovery-key',
    });
    expect(api.saveInferenceSettings).not.toHaveBeenCalled();
    expect(document.querySelectorAll('#agent-models option')).toHaveLength(2);
    await user.clear(screen.getByLabelText('Agent model'));
    await user.type(screen.getByLabelText('Agent model'), 'unlisted-model');
    expect(screen.getByLabelText('Agent model')).toHaveValue('unlisted-model');
  });

  it('keeps a manual-entry fallback and never displays a provider error that might contain a secret', async () => {
    vi.spyOn(api, 'inferenceModels').mockRejectedValue(new Error('upstream echoed secret-key'));
    vi.mocked(api.saveInferenceSettings).mockRejectedValue(new Error('upstream echoed secret-key'));
    const user = await open();
    await user.click(
      within(screen.getByRole('group', { name: 'Agent' })).getByRole('button', {
        name: 'Load models',
      }),
    );
    await screen.findByText(/Could not load models/);
    await user.type(screen.getByLabelText('Agent model'), '-manual');
    await user.click(screen.getByRole('button', { name: 'Save settings' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not save settings');
    expect(screen.getByLabelText('Agent model')).toHaveValue('coach-manual');
    expect(screen.queryByText(/secret-key/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save settings' })).toBeEnabled();
  });

  it('ignores a late discovery response for a URL that has been edited', async () => {
    let resolve!: (value: { models: string[] }) => void;
    vi.spyOn(api, 'inferenceModels').mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    const user = await open();
    await user.click(
      within(screen.getByRole('group', { name: 'Agent' })).getByRole('button', {
        name: 'Load models',
      }),
    );
    await user.clear(screen.getByLabelText('Agent base URL'));
    await user.type(screen.getByLabelText('Agent base URL'), 'http://localhost:9000/v1');
    await act(async () => {
      resolve({ models: ['old-private-model'] });
    });
    expect(document.querySelectorAll('#agent-models option')).toHaveLength(0);
    expect(screen.queryByText('old-private-model')).not.toBeInTheDocument();
  });

  it('allows clearing a complete service but rejects a half-configured service', async () => {
    const user = await open();
    await user.clear(screen.getByLabelText('Agent base URL'));
    await user.click(screen.getByRole('button', { name: 'Save settings' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Enter both a base URL and model for Agent',
    );
    expect(api.saveInferenceSettings).not.toHaveBeenCalled();
    await user.clear(screen.getByLabelText('Agent model'));
    await user.click(screen.getByRole('button', { name: 'Save settings' }));
    await waitFor(() =>
      expect(api.saveInferenceSettings).toHaveBeenCalledWith(
        expect.objectContaining({ agent: { base_url: '', model: '', api_key: '' } }),
      ),
    );
  });

  it('offers a retry when saved settings cannot be loaded', async () => {
    vi.mocked(api.inferenceSettings).mockRejectedValueOnce(new Error('not available'));
    render(<InferenceSettings />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load inference settings');
    await userEvent.click(screen.getByRole('button', { name: 'Retry loading settings' }));
    expect(await screen.findByLabelText('Agent base URL')).toHaveValue(saved.agent.base_url);
  });
});
