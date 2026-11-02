import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../lib/api';
import { Methodology } from './Methodology';

afterEach(() => vi.restoreAllMocks());
describe('methodology evidence', () => {
  it('shows saved training provenance and active runtime retrieval without inventing results', async () => {
    vi.spyOn(api, 'methodology').mockResolvedValue({
      status: 'not_evaluated',
      provider: 'llama',
      training: {
        status: 'not_trained',
        configuration: { base_model: 'Qwen/Qwen3-4B-Instruct-2507', lora_r: 32 },
        dataset_provenance: { human_reviews_completed: 0, source: 'Synthetic curriculum drafts' },
        model_card: { adapter_status: 'Not produced' },
      },
      evaluations: [],
      limitations: ['Training has not run.'],
    });
    vi.spyOn(api, 'health').mockResolvedValue({
      status: 'degraded',
      provider: 'llama',
      database: 'ready',
      llm: 'ready base model',
      speech: 'Azure not configured',
      retrieval: 'PostgreSQL full-text + HNSW; reranker unavailable',
    });
    render(<Methodology />);
    expect(
      await screen.findByText('PostgreSQL full-text + HNSW; reranker unavailable'),
    ).toBeInTheDocument();
    expect(screen.getByText('Qwen/Qwen3-4B-Instruct-2507')).toBeInTheDocument();
    expect(screen.getByText('Synthetic curriculum drafts')).toBeInTheDocument();
    expect(screen.getByText('Not produced')).toBeInTheDocument();
    expect(screen.getByText('No assessed results have been recorded yet.')).toBeInTheDocument();
  });
});
