import { Check, Circle, LoaderCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { formatDuration } from '../lib/format';
import './SetupPreparation.css';

export type StartupStage = 'profile' | 'question' | 'opening';
export function StartupProgress({
  stage,
  startedAt,
  uploaded,
}: {
  stage: StartupStage;
  startedAt: number;
  uploaded: boolean;
}) {
  const [elapsed, setElapsed] = useState(() => Math.floor((Date.now() - startedAt) / 1000));
  useEffect(() => {
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [startedAt]);
  const stages: { id: StartupStage; label: string }[] = [
    {
      id: 'profile',
      label: uploaded
        ? 'Uploading and indexing the job description'
        : 'Reading and indexing the job description',
    },
    { id: 'question', label: 'Preparing the first question' },
    { id: 'opening', label: 'Opening interview' },
  ];
  const active = stages.findIndex((item) => item.id === stage);
  return (
    <section className="startup-progress" aria-labelledby="startup-title">
      <div className="startup-heading">
        <h2 id="startup-title">Preparing your interview</h2>
        <span aria-label={`Elapsed time ${formatDuration(elapsed)}`}>
          Elapsed {formatDuration(elapsed)}
        </span>
      </div>
      <p className="startup-current" role="status">
        {stages[active].label}…
      </p>
      <div
        className="startup-progress-track"
        role="progressbar"
        aria-label="Interview preparation"
        aria-valuetext={stages[active].label}
      >
        <span />
      </div>
      <ol className="startup-stage-list">
        {stages.map((item, index) => (
          <li
            key={item.id}
            className={index === active ? 'active' : index < active ? 'complete' : ''}
            aria-current={index === active ? 'step' : undefined}
          >
            {index < active ? (
              <Check size={16} aria-hidden="true" />
            ) : index === active ? (
              <LoaderCircle size={16} className="spin" aria-hidden="true" />
            ) : (
              <Circle size={16} aria-hidden="true" />
            )}
            <span>{item.label}</span>
            <small>{index < active ? 'Done' : index === active ? 'In progress' : 'Waiting'}</small>
          </li>
        ))}
      </ol>
      {elapsed >= 15 && stage !== 'opening' && (
        <p className="startup-slow" role="status">
          {stage === 'profile'
            ? 'The document and retrieval services are still processing the job description.'
            : 'Your first question is still being prepared.'}{' '}
          Keep this page open; you do not need to press Start again.
        </p>
      )}
    </section>
  );
}
