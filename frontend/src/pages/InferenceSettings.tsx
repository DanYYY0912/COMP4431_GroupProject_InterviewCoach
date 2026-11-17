import {
  BrainCircuit,
  Check,
  Database,
  Download,
  KeyRound,
  LoaderCircle,
  Mic,
  Save,
  ShieldCheck,
  SlidersHorizontal,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api } from '../lib/api';
import type {
  InferenceComponent,
  InferenceSettings as SavedSettings,
  InferenceSettingsUpdate,
} from '../lib/types';
import { ErrorNotice, Loading } from '../components/Common';

const services = [
  {
    id: 'agent',
    name: 'Agent',
    icon: BrainCircuit,
    description: 'Interview questions, follow-ups and feedback.',
    fallback: 'Leave the base URL and model empty to use the scripted demo coach.',
  },
  {
    id: 'asr',
    name: 'ASR',
    icon: Mic,
    description: 'Turn recorded answers into editable transcripts.',
    fallback: 'Leave the base URL and model empty to use the native Whisper fallback.',
  },
  {
    id: 'embedding',
    name: 'Embedding',
    icon: Database,
    description: 'Find relevant job descriptions and source passages.',
    fallback: 'Leave the base URL and model empty to use lexical search.',
  },
  {
    id: 'reranker',
    name: 'Reranker',
    icon: SlidersHorizontal,
    description: 'Order retrieved passages by their relevance.',
    fallback: 'Leave the base URL and model empty to disable reranking.',
  },
] as const;
type ServiceDraft = { base_url: string; model: string; api_key: string; clear_key: boolean };
type Draft = Record<InferenceComponent, ServiceDraft>;
type Discovery = { loading: boolean; models: string[]; message: string; failed: boolean };
const emptyDiscovery = (): Discovery => ({
  loading: false,
  models: [],
  message: '',
  failed: false,
});
const initialDiscovery = () => ({
  agent: emptyDiscovery(),
  asr: emptyDiscovery(),
  embedding: emptyDiscovery(),
  reranker: emptyDiscovery(),
});

function draftFrom(saved: SavedSettings): Draft {
  return Object.fromEntries(
    services.map(({ id }) => [
      id,
      {
        base_url: saved[id].base_url,
        model: saved[id].model,
        api_key: '',
        clear_key: false,
      },
    ]),
  ) as Draft;
}
function submittedKey(
  draft: ServiceDraft,
  saved: SavedSettings[InferenceComponent],
): string | null {
  if (draft.api_key) return draft.api_key;
  return draft.clear_key || draft.base_url.trim() !== saved.base_url ? '' : null;
}

export function InferenceSettings() {
  const [saved, setSaved] = useState<SavedSettings | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [loadError, setLoadError] = useState('');
  const [saveError, setSaveError] = useState('');
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [discovery, setDiscovery] = useState(initialDiscovery);
  const modelRequests = useRef({ agent: 0, asr: 0, embedding: 0, reranker: 0 });
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    let active = true;
    setLoadError('');
    void api
      .inferenceSettings()
      .then((value) => {
        if (!active) return;
        setSaved(value);
        setDraft(draftFrom(value));
      })
      .catch(() => {
        if (active)
          setLoadError(
            'Could not load inference settings. Check that the app service is running and try again.',
          );
      });
    return () => {
      active = false;
    };
  }, [loadAttempt]);

  const dirty =
    !!saved &&
    !!draft &&
    services.some(({ id }) => {
      const entry = draft[id];
      return (
        entry.base_url.trim() !== saved[id].base_url ||
        entry.model.trim() !== saved[id].model ||
        !!entry.api_key ||
        (entry.clear_key && saved[id].api_key_set)
      );
    });

  function change(id: InferenceComponent, update: Partial<ServiceDraft>) {
    setDraft((current) => current && { ...current, [id]: { ...current[id], ...update } });
    setSuccess(false);
    setSaveError('');
    if ('base_url' in update || 'api_key' in update || 'clear_key' in update) {
      modelRequests.current[id]++;
      setDiscovery((current) => ({ ...current, [id]: emptyDiscovery() }));
    }
  }

  async function loadModels(id: InferenceComponent) {
    if (!draft || !saved || !draft[id].base_url.trim()) return;
    const requestId = ++modelRequests.current[id];
    setDiscovery((current) => ({ ...current, [id]: { ...emptyDiscovery(), loading: true } }));
    try {
      const result = await api.inferenceModels(id, {
        base_url: draft[id].base_url.trim(),
        api_key: submittedKey(draft[id], saved[id]),
      });
      if (!mounted.current || modelRequests.current[id] !== requestId) return;
      const models = [...new Set(result.models)].sort();
      setDiscovery((current) => ({
        ...current,
        [id]: {
          loading: false,
          models,
          failed: false,
          message: models.length
            ? `${models.length} ${models.length === 1 ? 'model' : 'models'} available. Choose one or enter a model name.`
            : 'No models were listed. Enter a model name manually.',
        },
      }));
    } catch {
      if (!mounted.current || modelRequests.current[id] !== requestId) return;
      setDiscovery((current) => ({
        ...current,
        [id]: {
          ...emptyDiscovery(),
          failed: true,
          message:
            'Could not load models. Check the URL and key, or enter a model name manually if this server does not list models.',
        },
      }));
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!draft || !saved || saving || !dirty) return;
    const incomplete = services.find(
      ({ id }) => !!draft[id].base_url.trim() !== !!draft[id].model.trim(),
    );
    if (incomplete) {
      setSaveError(`Enter both a base URL and model for ${incomplete.name}, or leave both empty.`);
      return;
    }
    const payload = Object.fromEntries(
      services.map(({ id }) => [
        id,
        {
          base_url: draft[id].base_url.trim(),
          model: draft[id].model.trim(),
          api_key: submittedKey(draft[id], saved[id]),
        },
      ]),
    ) as InferenceSettingsUpdate;
    setSaving(true);
    setSaveError('');
    setSuccess(false);
    try {
      const result = await api.saveInferenceSettings(payload);
      if (!mounted.current) return;
      setSaved(result);
      setDraft(draftFrom(result));
      setSuccess(true);
    } catch {
      if (mounted.current)
        setSaveError(
          'Could not save settings. Check the URLs and models, and wait for any active request to finish before trying again. Your changes are still here.',
        );
    } finally {
      if (mounted.current) setSaving(false);
    }
  }

  return (
    <>
      <div className="page-heading compact settings-heading">
        <div>
          <p className="eyebrow">YOUR WORKSPACE, YOUR MODELS</p>
          <h1>Inference settings</h1>
          <p className="lead">Choose the services behind your practice.</p>
        </div>
        <span className="settings-heading-icon">
          <SlidersHorizontal size={28} strokeWidth={1.5} />
        </span>
      </div>
      <div className="settings-privacy">
        <ShieldCheck size={21} />
        <p>
          Selected external servers receive prompts, audio or source passages for their task. API
          keys are stored locally on the app server and are never returned to this page.
        </p>
      </div>
      {loadError ? (
        <div className="settings-load-error">
          <ErrorNotice message={loadError} />
          <button
            type="button"
            className="button secondary"
            onClick={() => setLoadAttempt((value) => value + 1)}
          >
            Retry loading settings
          </button>
        </div>
      ) : !draft || !saved ? (
        <Loading label="Loading inference settings…" />
      ) : (
        <form onSubmit={save}>
          <div className="inference-grid">
            {services.map(({ id, name, description, fallback, icon: Icon }, index) => {
              const entry = draft[id];
              const urlChanged = entry.base_url.trim() !== saved[id].base_url;
              const existingKey = saved[id].api_key_set;
              const keyHelp = entry.api_key
                ? 'A new key will be stored when you save.'
                : entry.clear_key
                  ? 'The saved key will be cleared when you save.'
                  : urlChanged && existingKey
                    ? 'The base URL changed. The saved key will not be reused; enter a key if this server needs one.'
                    : existingKey
                      ? 'A key is saved. Leave blank to keep it, or clear it below.'
                      : 'Optional for local servers. No key is saved.';
              const listing = discovery[id];
              return (
                <fieldset
                  className="panel inference-card"
                  disabled={saving}
                  key={id}
                  aria-labelledby={`${id}-heading`}
                >
                  <legend className="visually-hidden">{name}</legend>
                  <div className="inference-card-heading">
                    <span className="inference-icon">
                      <Icon size={23} strokeWidth={1.6} />
                    </span>
                    <div>
                      <h2 id={`${id}-heading`}>{name}</h2>
                      <p>{description}</p>
                    </div>
                    <span className="inference-number">0{index + 1}</span>
                  </div>
                  <div className="inference-field">
                    <label htmlFor={`${id}-base-url`}>{name} base URL</label>
                    <input
                      id={`${id}-base-url`}
                      type="url"
                      value={entry.base_url}
                      placeholder="http://localhost:8001/v1"
                      autoComplete="off"
                      spellCheck={false}
                      onChange={(event) => change(id, { base_url: event.target.value })}
                      aria-describedby={`${id}-url-help`}
                    />
                    <p className="field-help" id={`${id}-url-help`}>
                      Include the API path if needed. Public services require HTTPS; local and
                      private network servers may use HTTP.
                    </p>
                  </div>
                  <div className="inference-field">
                    <label htmlFor={`${id}-api-key`}>{name} API key</label>
                    <div className="inference-key-field">
                      <KeyRound size={16} />
                      <input
                        id={`${id}-api-key`}
                        type="password"
                        value={entry.api_key}
                        autoComplete="new-password"
                        spellCheck={false}
                        placeholder={
                          existingKey && !urlChanged && !entry.clear_key
                            ? 'Saved key · leave blank to keep'
                            : 'Optional API key'
                        }
                        onChange={(event) =>
                          change(id, { api_key: event.target.value, clear_key: false })
                        }
                        aria-describedby={`${id}-key-help`}
                      />
                    </div>
                    <div className="inference-key-help">
                      <p className="field-help" id={`${id}-key-help`}>
                        {keyHelp}
                      </p>
                      {(existingKey || entry.api_key) && !entry.clear_key && (
                        <button
                          type="button"
                          className="text-button"
                          aria-label={`Clear ${name} API key`}
                          onClick={() => change(id, { api_key: '', clear_key: true })}
                        >
                          Clear key
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="inference-field">
                    <div className="inference-model-label">
                      <label htmlFor={`${id}-model`}>{name} model</label>
                      <button
                        type="button"
                        className="text-button"
                        disabled={!entry.base_url.trim() || listing.loading}
                        onClick={() => void loadModels(id)}
                      >
                        {listing.loading ? (
                          <LoaderCircle size={14} className="spin" />
                        ) : (
                          <Download size={14} />
                        )}
                        {listing.loading ? 'Loading models…' : 'Load models'}
                      </button>
                    </div>
                    <input
                      id={`${id}-model`}
                      list={`${id}-models`}
                      value={entry.model}
                      placeholder="Choose or enter a model name"
                      autoComplete="off"
                      spellCheck={false}
                      onChange={(event) => change(id, { model: event.target.value })}
                      aria-describedby={`${id}-model-help`}
                    />
                    <datalist id={`${id}-models`}>
                      {listing.models.map((model) => (
                        <option value={model} key={model} />
                      ))}
                    </datalist>
                    <p
                      className={`field-help ${listing.failed ? 'model-discovery-error' : ''}`}
                      id={`${id}-model-help`}
                      role={listing.message ? 'status' : undefined}
                    >
                      {listing.message || 'Load available models, or enter the exact model name.'}
                    </p>
                  </div>
                  <p className="inference-fallback">{fallback}</p>
                </fieldset>
              );
            })}
          </div>
          {saveError && <ErrorNotice message={saveError} />}
          <div className="settings-save-bar">
            <div role="status" className="settings-save-status">
              {saving ? (
                <>
                  <LoaderCircle size={17} className="spin" />
                  <span>Saving settings…</span>
                </>
              ) : success ? (
                <>
                  <Check size={18} />
                  <span>Settings saved. New requests use these settings immediately.</span>
                </>
              ) : (
                <span>
                  {dirty
                    ? 'You have unsaved changes.'
                    : 'Changes apply to new requests. No restart needed.'}
                </span>
              )}
            </div>
            <button type="submit" className="button primary" disabled={saving || !dirty}>
              {saving ? <LoaderCircle size={17} className="spin" /> : <Save size={17} />}
              {saving ? 'Saving settings…' : 'Save settings'}
            </button>
          </div>
        </form>
      )}
    </>
  );
}
