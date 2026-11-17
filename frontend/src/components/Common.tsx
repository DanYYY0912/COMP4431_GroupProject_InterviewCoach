import { AlertCircle, ArrowUpRight, BookOpen, Check, LoaderCircle } from 'lucide-react';
import type { Citation, Health } from '../lib/types';

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
          : 'Local AI coach'}
    </span>
  );
}
// Health strings carry operator detail ("ready (local model; …)"); show only the status.
function shortStatus(status: string | undefined) {
  return status ? status.replace(/\s*\(.*\)\s*$/, '') : 'Checking…';
}

// "Azure not configured; local Whisper ready" -> "Local Whisper ready".
function readyPart(status: string | undefined) {
  if (!status) return 'Optional';
  const ready = status
    .split(';')
    .map((part) => part.trim())
    .find((part) => /ready/i.test(part));
  const label = ready ?? status;
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function Preflight({ health }: { health: Health | null }) {
  return (
    <div className="preflight">
      <div>
        <span className="status-dot" />
        <strong>Practice readiness</strong>
      </div>
      <ul>
        <li>
          <Check size={16} /> Local storage <span>{health?.database || 'Checking…'}</span>
        </li>
        <li>
          <Check size={16} /> Interview coach{' '}
          <span>{health?.provider === 'demo' ? 'Scripted demo' : shortStatus(health?.llm)}</span>
        </li>
        <li>
          <ArrowUpRight size={16} /> Voice services <span>{readyPart(health?.speech)}</span>
        </li>
      </ul>
    </div>
  );
}
