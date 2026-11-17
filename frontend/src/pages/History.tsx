import { ArrowRight, BriefcaseBusiness, Download, Play, Plus, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, errorMessage } from '../lib/api';
import { formatDate } from '../lib/format';
import { downloadSession } from '../lib/sessionExport';
import type { Session } from '../lib/types';
import { ErrorNotice, Loading } from '../components/Common';
import { SessionComparison } from '../components/SessionComparison';

export function History({ navigate }: { navigate: (path: string) => void }) {
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
      <div className="page-heading compact simple-heading">
        <h1>History</h1>
        <button className="button secondary" onClick={() => navigate('/setup')}>
          <Plus size={16} /> New practice
        </button>
      </div>
      {error && <ErrorNotice message={error} onDismiss={() => setError('')} />}
      <section className="history-section">
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
              <h3>No saved sessions.</h3>
              <p>Completed and in-progress interviews will appear here.</p>
            </div>
            <button className="text-button" onClick={() => navigate('/setup')}>
              New practice <ArrowRight size={18} />
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
    </>
  );
}
