import { AlertCircle, BookOpen, LoaderCircle } from 'lucide-react';
import type { Citation } from '../lib/types';

export function Loading({ label = 'Getting your practice ready…' }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <LoaderCircle size={24} className="spin" />
      <p>{label}</p>
    </div>
  );
}
export function ErrorNotice({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  return (
    <div className="notice error" role="alert">
      <AlertCircle size={19} />
      <span>{message}</span>
      {onDismiss && (
        <button className="text-button" onClick={onDismiss}>
          Dismiss
        </button>
      )}
    </div>
  );
}
export function Sources({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null;
  return (
    <details className="sources">
      <summary>
        <BookOpen size={15} /> View {citations.length} supporting{' '}
        {citations.length === 1 ? 'source' : 'sources'}
      </summary>
      <div className="source-list">
        {citations.map((c, i) => (
          <blockquote key={`${c.chunk_id}-${i}`}>
            <span className="eyebrow">
              {c.source} · {c.chunk_id}
            </span>
            <p>{c.text}</p>
          </blockquote>
        ))}
      </div>
    </details>
  );
}
export function ProviderBadge({ provider }: { provider?: string }) {
  return (
    <span className="provider-badge">
      <span className="status-dot" />
      {provider === 'demo-fallback'
        ? 'Fallback coach · scripted'
        : provider === 'demo' || !provider
          ? 'Demo coach · scripted'
          : provider === 'openai' || provider === 'openai-compatible'
            ? 'Configured AI coach'
            : 'Local AI coach'}
    </span>
  );
}
