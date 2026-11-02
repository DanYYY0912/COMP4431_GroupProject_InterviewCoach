import {
  ArrowRight,
  ArrowUpRight,
  AudioLines,
  BriefcaseBusiness,
  Clock3,
  Download,
  FileText,
  Languages,
  Play,
  Plus,
  Trash2,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, errorMessage } from '../lib/api';
import { formatDate } from '../lib/format';
import { downloadSession } from '../lib/sessionExport';
import type { Session } from '../lib/types';
import { ErrorNotice, Loading } from '../components/Common';
import { SessionComparison } from '../components/SessionComparison';

export function Dashboard({ navigate }: { navigate: (path: string) => void }) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selection, setSelection] = useState<string[]>([]);
  const [exporting, setExporting] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    api
      .sessions()
      .then((data) => {
        if (active) setSessions(data);
      })
      .catch((e) => {
        if (active) setError(errorMessage(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  const completed = sessions.filter((s) => s.state === 'completed');
  const compared = selection
    .map((id) => completed.find((session) => session.id === id))
    .filter((session): session is Session => !!session);
  const answered = sessions.flatMap((s) => s.turns).filter((t) => t.answer).length;
  async function remove(session: Session) {
    if (
      !window.confirm(`Delete this ${session.role_title} practice and its transcript permanently?`)
    )
      return;
    try {
      await api.delete(session.id);
      setSessions((current) => current.filter((s) => s.id !== session.id));
      setSelection((current) => current.filter((id) => id !== session.id));
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  async function exportSession(id: string) {
    setExporting(id);
    try {
      await downloadSession(id);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setExporting(null);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">YOUR PRACTICE SPACE</p>
          <h1>
            A little practice.
            <br />A lot more <em>confidence.</em>
          </h1>
          <p className="lead">Find your voice for your next opportunity.</p>
        </div>
        <span className="language-stamp">
          <Languages size={20} /> English & 廣東話
        </span>
      </div>
      {error && <ErrorNotice message={error} onDismiss={() => setError('')} />}
      <section className="dashboard-hero" aria-labelledby="hero-title">
        <div className="hero-copy">
          <span className="pill light">
            <span className="status-dot" /> MADE FOR HONG KONG GRADUATES
          </span>
          <h2 id="hero-title">
            Your next chapter
            <br />
            starts with a conversation.
          </h2>
          <p>
            Bring a job description. Practise the questions that matter. Leave with a clearer story
            to tell.
          </p>
          <button className="button lime" onClick={() => navigate('/setup')}>
            Start a practice interview <ArrowUpRight size={19} />
          </button>
          <span className="hero-note">
            <Clock3 size={14} /> Your pace, your language. Start with 3 questions.
          </span>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="orbital orbit-one" />
          <div className="orbital orbit-two" />
          <div className="voice-sphere">
            <AudioLines strokeWidth={1.25} />
          </div>
          <span className="floating-note english">“Tell me about a time…”</span>
          <span className="floating-note cantonese">「分享一次你解決問題嘅經驗。」</span>
          <span className="art-label">A SPACE TO FIND YOUR VOICE</span>
        </div>
      </section>
      <section className="stats-row" aria-label="Practice overview">
        <div>
          <span className="stat-icon">
            <BriefcaseBusiness size={19} />
          </span>
          <strong>{sessions.length}</strong>
          <span>Practice sessions</span>
        </div>
        <div>
          <span className="stat-icon">
            <AudioLines size={19} />
          </span>
          <strong>{answered}</strong>
          <span>Answers explored</span>
        </div>
        <div>
          <span className="stat-icon">
            <FileText size={19} />
          </span>
          <strong>{completed.length}</strong>
          <span>Debriefs ready</span>
        </div>
      </section>
      <section className="history-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">KEEP THE MOMENTUM</p>
            <h2>Your recent practice</h2>
          </div>
          <button className="text-button" onClick={() => navigate('/setup')}>
            <Plus size={16} /> New practice
          </button>
        </div>
        {completed.length >= 2 && (
          <p className="history-help">
            Select two completed sessions to compare their evidence and feedback.
          </p>
        )}
        {loading ? (
          <Loading label="Loading your practice history…" />
        ) : sessions.length ? (
          <div className="session-list">
            {sessions.map((session) => (
              <article className="session-row" key={session.id}>
                <div className="session-icon">
                  <BriefcaseBusiness size={21} />
                </div>
                <div className="session-info">
                  <h3>{session.role_title}</h3>
                  <p>
                    {formatDate(session.created_at)} <span>·</span>{' '}
                    {session.language === 'zh-HK' ? '廣東話' : 'English'} <span>·</span>{' '}
                    {session.turns.filter((t) => t.answer).length}/{session.question_count} answers
                  </p>
                </div>
                <span className={`pill ${session.state === 'completed' ? 'complete' : 'neutral'}`}>
                  {session.state === 'completed' ? 'Completed' : 'In progress'}
                </span>
                <button
                  className="button small secondary"
                  onClick={() =>
                    navigate(
                      `/${session.state === 'completed' ? 'report' : 'interview'}/${session.id}`,
                    )
                  }
                >
                  {session.state === 'completed' ? 'View debrief' : 'Continue'}{' '}
                  <ArrowRight size={16} />
                </button>
                <button
                  className="icon-button"
                  aria-label={`Export full session for ${session.role_title}`}
                  title="Download saved questions, transcript and debrief"
                  disabled={exporting !== null}
                  onClick={() => void exportSession(session.id)}
                >
                  <Download size={16} />
                </button>
                <button
                  className="icon-button delete-button"
                  aria-label={`Delete ${session.role_title} session`}
                  onClick={() => void remove(session)}
                >
                  <Trash2 size={16} />
                </button>
                {session.state === 'completed' && completed.length >= 2 && (
                  <label className="compare-select">
                    <input
                      type="checkbox"
                      aria-label={`Compare ${session.role_title} from ${formatDate(session.created_at)}`}
                      checked={selection.includes(session.id)}
                      disabled={selection.length >= 2 && !selection.includes(session.id)}
                      onChange={(event) =>
                        setSelection((current) =>
                          event.target.checked
                            ? [...current, session.id].slice(0, 2)
                            : current.filter((id) => id !== session.id),
                        )
                      }
                    />
                    Compare
                  </label>
                )}
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-history">
            <div className="empty-icon">
              <Play size={21} />
            </div>
            <div>
              <h3>A fresh start looks good on you.</h3>
              <p>Your sessions and feedback will appear here. Ready when you are.</p>
            </div>
            <button className="text-button" onClick={() => navigate('/setup')}>
              Let’s begin <ArrowRight size={18} />
            </button>
          </div>
        )}
      </section>
      {compared.length === 1 && (
        <p className="comparison-prompt" role="status">
          Choose one more completed session to open the comparison.
        </p>
      )}
      {compared.length === 2 && (
        <SessionComparison
          key={`${compared[0].id}:${compared[1].id}`}
          left={compared[0]}
          right={compared[1]}
          onClear={() => setSelection([])}
        />
      )}
      <section className="practice-tip">
        <span className="tip-mark">✳</span>
        <div>
          <p className="eyebrow">A SMALL TIP, A STRONGER ANSWER</p>
          <p>
            Make it a story: set the <strong>situation</strong>, explain your <strong>task</strong>,
            describe your <strong>action</strong>, and share the <strong>result</strong>.
          </p>
        </div>
        <span className="star-word">S · T · A · R</span>
      </section>
    </>
  );
}
