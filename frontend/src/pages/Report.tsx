import {
  ArrowLeft,
  ArrowRight,
  Check,
  Download,
  MessageCircle,
  RotateCcw,
  Sparkles,
  Target,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, errorMessage } from '../lib/api';
import { exportJson, formatDuration } from '../lib/format';
import type { Report as ReportType } from '../lib/types';
import { ErrorNotice, Loading, Sources } from '../components/Common';

export function Report({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const [report, setReport] = useState<ReportType | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    api
      .report(id)
      .then((data) => {
        if (active) setReport(data);
      })
      .catch((e) => {
        if (active) setError(errorMessage(e));
      });
    return () => {
      active = false;
    };
  }, [id]);
  async function retry() {
    setBusy(true);
    try {
      const session = await api.control(id, 'retry');
      navigate(`/interview/${session.id}`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }
  if (!report)
    return error ? (
      <ErrorNotice message={error} />
    ) : (
      <Loading label="Bringing your feedback together…" />
    );
  const metrics = report.speech_metrics;
  const elements = report.star.filter((s) => s.present).length;
  return (
    <>
      <button className="back-link" onClick={() => navigate('/')}>
        <ArrowLeft size={16} /> Back to your practice space
      </button>
      <div className="page-heading compact">
        <div>
          <p className="eyebrow">YOUR SESSION DEBRIEF</p>
          <h1>
            Make your next
            <br />
            answer <em>stronger.</em>
          </h1>
          <p className="lead">
            {report.role_title} <span className="inline-dot">·</span>{' '}
            {report.language === 'zh-HK' ? '廣東話' : 'English'}
          </p>
        </div>
        <button
          className="button secondary"
          onClick={() => exportJson(report, `voxprep-debrief-${id}.json`)}
        >
          <Download size={17} /> Export report
        </button>
      </div>
      {error && <ErrorNotice message={error} onDismiss={() => setError('')} />}
      <section className="report-summary">
        <span className="summary-icon">
          <Sparkles size={24} />
        </span>
        <div>
          <p className="eyebrow">PRACTICE IS PROGRESS</p>
          <h2>{report.summary}</h2>
          <p>Feedback on the evidence in your answers — a guide for your next practice.</p>
        </div>
        <div className="answer-total">
          <strong>{metrics.answer_count}</strong>
          <span>answers explored</span>
        </div>
      </section>
      <div className="report-grid">
        <section className="panel star-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">THE SHAPE OF YOUR STORY</p>
              <h2>Your STAR evidence</h2>
            </div>
            <span className="pill neutral">{elements} of 4 elements found</span>
          </div>
          <div className="star-elements">
            {report.star.map((item) => (
              <details
                key={item.element}
                className={`star-element ${item.present ? 'present' : ''}`}
                open={!item.present}
              >
                <summary>
                  <span className="star-initial">{item.element[0]}</span>
                  <strong>{item.element}</strong>
                  <span>
                    {item.present ? (
                      <>
                        <Check size={15} /> Evidence found
                      </>
                    ) : (
                      'Room to develop'
                    )}
                  </span>
                </summary>
                <div>
                  <p>{item.evidence || 'No clear evidence was found in this session.'}</p>
                  <p className="coaching-text">{item.coaching}</p>
                </div>
              </details>
            ))}
          </div>
          <p className="field-help">
            Evidence detection is an aid to reflection, not a grade. Check the cited wording
            yourself.
          </p>
        </section>
        <aside className="improvement-card">
          <div className="improvement-icon">
            <Target size={25} />
          </div>
          <p className="eyebrow">ONE THING TO TRY NEXT</p>
          <h2>{report.prioritized_improvement}</h2>
          <div className="retry-exercise">
            <span>YOUR RETRY EXERCISE</span>
            <p>{report.retry_exercise}</p>
          </div>
          <button className="button lime full" disabled={busy} onClick={() => void retry()}>
            <RotateCcw size={17} /> {busy ? 'Preparing your retry…' : 'Practise this again'}
          </button>
        </aside>
      </div>
      <section className="panel competency-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">CONNECTED TO THE ROLE</p>
            <h2>Your competency evidence</h2>
          </div>
          <MessageCircle size={25} />
        </div>
        {report.competencies.length ? (
          report.competencies.map((c, i) => (
            <article className="competency-evidence" key={`${c.name}-${i}`}>
              <h3>{c.name}</h3>
              <div>
                {c.evidence && <blockquote>“{c.evidence}”</blockquote>}
                <p>{c.feedback}</p>
                <Sources citations={c.citations} />
              </div>
            </article>
          ))
        ) : (
          <p>Your next session will help you gather more specific examples for this role.</p>
        )}
      </section>
      <div className="report-grid lower">
        <section className="panel">
          <p className="eyebrow">KEEP DOING THIS</p>
          <h2>Your strengths</h2>
          <ul className="strengths-list">
            {report.strengths.map((s, i) => (
              <li key={i}>
                <Check size={18} />
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="panel">
          <p className="eyebrow">A LITTLE SELF-AWARENESS</p>
          <h2>Answer rhythm</h2>
          <div className="rhythm-grid">
            <div>
              <strong>
                {metrics.words_per_minute === null ? '—' : Math.round(metrics.words_per_minute)}
              </strong>
              <span>words / minute</span>
            </div>
            <div>
              <strong>{formatDuration(metrics.duration_seconds)}</strong>
              <span>total answer time</span>
            </div>
            <div>
              <strong>{metrics.filler_count}</strong>
              <span>filler words found</span>
            </div>
            <div>
              <strong>{metrics.pause_count ?? '—'}</strong>
              <span>recorded pauses</span>
            </div>
          </div>
          <p className="field-help">
            Typed-answer pace is not a speech measurement. Cantonese token counts differ from
            English words; pauses are shown only when measured from audio.
          </p>
        </section>
      </div>
      <section className="report-footnotes">
        <Sources citations={report.citations} />
        <details>
          <summary>How to read this feedback</summary>
          <ul>
            {report.limitations.map((text, i) => (
              <li key={i}>{text}</li>
            ))}
          </ul>
        </details>
      </section>
      <div className="report-footer">
        <p>Every attempt gives you something to build on.</p>
        <button className="button primary" onClick={() => navigate('/setup')}>
          Try another opportunity <ArrowRight size={17} />
        </button>
      </div>
    </>
  );
}
