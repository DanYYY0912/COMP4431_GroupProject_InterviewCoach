import {
  BookOpen,
  CheckCircle2,
  CircleDashed,
  Database,
  FlaskConical,
  GitBranch,
  ShieldCheck,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, errorMessage } from '../lib/api';
import type { Health, Methodology as MethodologyData } from '../lib/types';
import { ErrorNotice, Loading } from '../components/Common';

const pipeline = [
  ['Job description', 'Your role becomes retrievable passages.'],
  ['Retrieve context', 'Relevant competencies and STAR guidance.'],
  ['Coach & validate', 'Structured questions, checked before display.'],
  ['Reflect & retry', 'Feedback connected to your own evidence.'],
];
function display(value: unknown) {
  if (value === null || value === undefined) return 'Not recorded';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}
function MetadataRecord({ value }: { value: unknown }) {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    return <p className="field-help">No saved record is available.</p>;
  return (
    <dl className="record-list">
      {Object.entries(value).map(([key, item]) => (
        <div key={key}>
          <dt>{key.replaceAll('_', ' ')}</dt>
          <dd>
            <pre>{display(item)}</pre>
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function Methodology() {
  const [data, setData] = useState<MethodologyData | null>(null);
  const [error, setError] = useState('');
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState('');
  useEffect(() => {
    let active = true;
    void Promise.allSettled([api.methodology(), api.health()]).then(([record, runtime]) => {
      if (!active) return;
      if (record.status === 'fulfilled') setData(record.value);
      else setError(errorMessage(record.reason));
      if (runtime.status === 'fulfilled') setHealth(runtime.value);
      else
        setHealthError('Runtime health could not be checked. Saved methodology remains available.');
    });
    return () => {
      active = false;
    };
  }, []);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">UNDER THE SURFACE</p>
          <h1>
            Built to practise.
            <br />
            <em>Open to scrutiny.</em>
          </h1>
          <p className="lead">
            How your coach works, what has been measured, and what is still to come.
          </p>
        </div>
        <FlaskConical className="heading-icon" size={48} strokeWidth={1.3} />
      </div>
      {error && <ErrorNotice message={error} />}
      <section className="method-pipeline" aria-label="Interview processing pipeline">
        {pipeline.map(([title, description], i) => (
          <article key={title}>
            <span>0{i + 1}</span>
            <h2>{title}</h2>
            <p>{description}</p>
          </article>
        ))}
      </section>
      {!data ? (
        !error && <Loading label="Loading the methodology record…" />
      ) : (
        <>
          <div className="method-status">
            <span className="pill neutral">
              <CircleDashed size={14} /> {data.status.replaceAll('_', ' ')}
            </span>
            <p>
              Current coach:{' '}
              <strong>
                {data.provider === 'demo' ? 'Scripted demonstration provider' : data.provider}
              </strong>
              . A working interface does not establish model quality or prove fine-tuning.
            </p>
          </div>
          <div className="report-grid">
            <section className="panel">
              <GitBranch size={24} />
              <h2>Model & training record</h2>
              <p>
                Training requires human-reviewed bilingual examples, isolated data splits and a CUDA
                GPU. Draft examples do not count as approved training material. The saved records
                below identify the base model and distinguish configuration from completed training.
              </p>
              <dl className="record-list">
                {Object.entries(data.training)
                  .filter(
                    ([key]) => !['configuration', 'dataset_provenance', 'model_card'].includes(key),
                  )
                  .map(([key, value]) => (
                    <div key={key}>
                      <dt>{key.replaceAll('_', ' ')}</dt>
                      <dd>
                        <pre>{display(value)}</pre>
                      </dd>
                    </div>
                  ))}
              </dl>
              <details className="method-detail">
                <summary>Inspect the saved QLoRA configuration</summary>
                <MetadataRecord value={data.training.configuration} />
              </details>
              <details className="method-detail">
                <summary>Dataset provenance & human review</summary>
                <MetadataRecord value={data.training.dataset_provenance} />
              </details>
              <details className="method-detail">
                <summary>Model card & intended use</summary>
                <MetadataRecord value={data.training.model_card} />
              </details>
            </section>
            <section className="panel">
              <Database size={24} />
              <h2>Grounding & evidence</h2>
              <p>
                Job descriptions are treated as quoted source material. Feedback cites source chunks
                and answer excerpts so you can inspect the evidence.
              </p>
              <ul className="method-list">
                <li>
                  <CheckCircle2 size={17} /> Source text stays inspectable beside coaching.
                </li>
                <li>
                  <CheckCircle2 size={17} /> Model responses pass a typed schema boundary.
                </li>
                <li>
                  <CircleDashed size={17} /> Retrieval scores require a held-out benchmark.
                </li>
                <li>
                  <CircleDashed size={17} /> Claimed improvements require measured comparisons.
                </li>
              </ul>
              <p className="field-help">
                Runtime readiness below is checked on this computer. It is separate from measured
                quality; the development fallback may use lexical search instead of embeddings.
              </p>
              {healthError ? (
                <p className="speech-notice" role="status">
                  {healthError}
                </p>
              ) : health ? (
                <dl className="record-list runtime-health">
                  <div>
                    <dt>Active retrieval</dt>
                    <dd>{health.retrieval}</dd>
                  </div>
                  <div>
                    <dt>Local model</dt>
                    <dd>{health.llm}</dd>
                  </div>
                  <div>
                    <dt>Database</dt>
                    <dd>{health.database}</dd>
                  </div>
                  <div>
                    <dt>Speech services</dt>
                    <dd>{health.speech}</dd>
                  </div>
                </dl>
              ) : (
                <p className="field-help" role="status">
                  Checking runtime readiness…
                </p>
              )}
            </section>
          </div>
          <section className="panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">EVIDENCE, NOT ASSUMPTIONS</p>
                <h2>Evaluation results</h2>
              </div>
              <BookOpen size={24} />
            </div>
            {data.evaluations.length ? (
              <div className="evaluation-results">
                {data.evaluations.map((evaluation, i) => (
                  <details key={i}>
                    <summary>
                      {typeof evaluation.name === 'string'
                        ? evaluation.name
                        : `Evaluation record ${i + 1}`}
                    </summary>
                    <pre>{JSON.stringify(evaluation, null, 2)}</pre>
                  </details>
                ))}
              </div>
            ) : (
              <div className="empty-evaluation">
                <CircleDashed size={28} />
                <h3>No assessed results have been recorded yet.</h3>
                <p>
                  Model comparisons, retrieval recall, speech accuracy, latency, and peer usability
                  results appear here only after the evaluation scripts have produced real evidence.
                </p>
              </div>
            )}
          </section>
          <section className="privacy-panel">
            <ShieldCheck size={30} />
            <div>
              <h2>Practice with clear boundaries.</h2>
              <p>
                VoxPrep is a learning tool. It does not rank candidates or rate appearance, accent
                quality, personality, or employability. Session storage is local. Azure voice is
                optional and requires consent.
              </p>
              <ul>
                {data.limitations.map((limitation, i) => (
                  <li key={i}>{limitation}</li>
                ))}
              </ul>
            </div>
          </section>
        </>
      )}
    </>
  );
}
