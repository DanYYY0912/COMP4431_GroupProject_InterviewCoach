import { useEffect, useState } from 'react';
import { Check, Columns2, X } from 'lucide-react';
import { api, errorMessage } from '../lib/api';
import { formatDate, formatDuration } from '../lib/format';
import type { Report, Session } from '../lib/types';
import { ErrorNotice, Loading, ProviderBadge, Sources } from './Common';

function ComparisonColumn({
  session,
  report,
  position,
}: {
  session: Session;
  report: Report;
  position: 'First' | 'Second';
}) {
  return (
    <article
      className="comparison-column"
      aria-label={`${position} session: ${session.role_title}`}
    >
      <header>
        <p className="eyebrow">
          {position.toUpperCase()} SESSION · {formatDate(session.created_at)}
        </p>
        <h3>{session.role_title}</h3>
        <div className="comparison-meta">
          <span>{session.language === 'zh-HK' ? '廣東話' : 'English'}</span>
          <span>{session.difficulty}</span>
          <ProviderBadge provider={session.provider} />
        </div>
      </header>
      <dl className="comparison-observations">
        <div>
          <dt>Saved answers</dt>
          <dd>
            {report.speech_metrics.answer_count} / {session.question_count}
          </dd>
        </div>
        <div>
          <dt>Answer time</dt>
          <dd>{formatDuration(report.speech_metrics.duration_seconds)}</dd>
        </div>
      </dl>
      <section aria-label="STAR evidence">
        <h4>STAR evidence</h4>
        <div className="comparison-star">
          {report.star.map((element) => (
            <details key={element.element} open>
              <summary>
                <strong>{element.element}</strong>
                <span>
                  {element.present ? (
                    <>
                      <Check size={14} /> Evidence found
                    </>
                  ) : (
                    'Room to develop'
                  )}
                </span>
              </summary>
              <p>{element.evidence || 'No clear evidence was found.'}</p>
              <p className="comparison-coaching">{element.coaching}</p>
            </details>
          ))}
        </div>
      </section>
      <section aria-label="Competency feedback">
        <h4>Competency feedback</h4>
        {report.competencies.length ? (
          report.competencies.map((competency, index) => (
            <details className="comparison-competency" key={`${competency.name}-${index}`} open>
              <summary>{competency.name}</summary>
              {competency.evidence && <blockquote>{competency.evidence}</blockquote>}
              <p>{competency.feedback}</p>
              <Sources citations={competency.citations} />
            </details>
          ))
        ) : (
          <p>No competency feedback was recorded.</p>
        )}
      </section>
      <section className="comparison-next">
        <h4>Next practice focus</h4>
        <p>{report.prioritized_improvement}</p>
      </section>
      {!!report.limitations.length && (
        <details className="comparison-limitations">
          <summary>Session limitations</summary>
          <ul>
            {report.limitations.map((text, index) => (
              <li key={index}>{text}</li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}

export function SessionComparison({
  left,
  right,
  onClear,
}: {
  left: Session;
  right: Session;
  onClear: () => void;
}) {
  const [reports, setReports] = useState<[Report, Report] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    Promise.all([api.report(left.id), api.report(right.id)])
      .then((data) => {
        if (active) setReports(data);
      })
      .catch((e) => {
        if (active) setError(errorMessage(e));
      });
    return () => {
      active = false;
    };
  }, [left.id, right.id]);
  return (
    <section className="session-comparison" aria-labelledby="comparison-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">NOTICE WHAT CHANGED</p>
          <h2 id="comparison-heading">
            <Columns2 size={20} /> Compare your practice
          </h2>
        </div>
        <button className="text-button" onClick={onClear}>
          <X size={16} /> Clear comparison
        </button>
      </div>
      <p className="comparison-context">
        Read differences in the context of each role, language and answer count. Evidence detection
        is a reflection aid; answer time also includes typed responses.
      </p>
      {error ? (
        <ErrorNotice message={error} />
      ) : reports ? (
        <div className="comparison-columns">
          <ComparisonColumn session={left} report={reports[0]} position="First" />
          <ComparisonColumn session={right} report={reports[1]} position="Second" />
        </div>
      ) : (
        <Loading label="Loading both saved debriefs…" />
      )}
    </section>
  );
}
