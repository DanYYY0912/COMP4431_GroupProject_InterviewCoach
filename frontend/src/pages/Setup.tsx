import { ArrowRight, ArrowUpRight, Check, FileUp, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api, errorMessage } from '../lib/api';
import type { Health, Language } from '../lib/types';
import { ErrorNotice } from '../components/Common';
import { AppearanceSelector } from '../components/AppearanceSelector';
import { StartupProgress } from '../components/StartupProgress';
import type { StartupStage } from '../components/StartupProgress';
import {
  getInterviewer,
  readInterviewerPreference,
  saveInterviewerPreference,
} from '../lib/interviewers';
import type { InterviewerId } from '../lib/interviewers';

const sample = `Graduate Software Engineer — Hong Kong\nJoin a product team building reliable web applications for local businesses.\nResponsibilities: build Python REST APIs and React interfaces; design SQL database queries; write automated tests; debug production issues with the team; communicate trade-offs clearly in English and Cantonese.\nRequirements: a degree in computer science or a related subject, practical knowledge of Python or JavaScript, Git and data structures, teamwork, curiosity, and evidence of a project where you solved a technical problem.\nWe value thoughtful problem solving, clear communication, and measurable improvements to software quality.`;

export function Setup({ navigate }: { navigate: (path: string) => void }) {
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [language, setLanguage] = useState<Language>('en-HK');
  const [difficulty, setDifficulty] = useState('standard');
  const [questions, setQuestions] = useState(5);
  const [interviewer, setInterviewer] = useState<InterviewerId>(readInterviewerPreference);
  const [preparation, setPreparation] = useState<{ stage: StartupStage; startedAt: number } | null>(
    null,
  );
  const busy = preparation !== null;
  const submitting = useRef(false);
  const mounted = useRef(true);
  const [error, setError] = useState('');
  const [health, setHealth] = useState<Health | null>(null);
  const [healthUnavailable, setHealthUnavailable] = useState(false);
  const jobReady = !!file || text.trim().length >= 40;
  const valid =
    jobReady &&
    ['en-HK', 'zh-HK'].includes(language) &&
    ['foundation', 'standard', 'stretch'].includes(difficulty) &&
    [3, 5, 8].includes(questions);
  useEffect(() => {
    mounted.current = true;
    let active = true;
    void api
      .health()
      .then((result) => {
        if (active) setHealth(result);
      })
      .catch(() => {
        if (active) setHealthUnavailable(true);
      });
    return () => {
      active = false;
      mounted.current = false;
    };
  }, []);
  async function start(event: FormEvent) {
    event.preventDefault();
    if (!valid || submitting.current) return;
    submitting.current = true;
    saveInterviewerPreference(interviewer);
    setPreparation({ stage: 'profile', startedAt: Date.now() });
    setError('');
    try {
      const profile = await api.profile(text, file);
      // Finish the requested session even after leaving, so the saved job has a History entry.
      if (mounted.current)
        setPreparation((current) => current && { ...current, stage: 'question' });
      const session = await api.create(profile.id, language, difficulty, questions, interviewer);
      if (!mounted.current) return;
      setPreparation((current) => current && { ...current, stage: 'opening' });
      navigate(`/interview/${session.id}`);
    } catch (e) {
      if (!mounted.current) return;
      setError(errorMessage(e));
      setPreparation(null);
      submitting.current = false;
    }
  }
  function chooseFile(selected: File | null) {
    if (selected && (selected.size === 0 || selected.size > 5 * 1024 * 1024)) {
      setError('Choose a nonempty document no larger than 5 MB.');
      return;
    }
    if (selected && !/\.(pdf|docx|txt)$/i.test(selected.name)) {
      setError('Please use a text-based PDF, DOCX, or TXT file.');
      return;
    }
    setError('');
    setFile(selected);
  }
  return (
    <>
      <div className="page-heading compact simple-heading">
        <h1>Practice interview</h1>
      </div>
      <form className="setup-grid" onSubmit={start}>
        <div className="setup-main">
          <section className="panel">
            <div className="section-heading">
              <h2 id="job-heading">Job description</h2>
              <button
                className="text-button"
                type="button"
                disabled={busy}
                onClick={() => {
                  setText(sample);
                  setFile(null);
                  setError('');
                }}
              >
                Try a sample role
              </button>
            </div>
            <label className="visually-hidden" htmlFor="job-text">
              Job description
            </label>
            <p className="field-help" id="job-help">
              Paste at least 40 characters, or upload a text-based document.
            </p>
            <textarea
              id="job-text"
              aria-describedby="job-help"
              rows={9}
              value={text}
              disabled={!!file || busy}
              onChange={(e) => setText(e.target.value)}
              placeholder="Role, responsibilities and required skills"
              maxLength={50000}
            />
            <div className="upload-row">
              <label className="upload-button" htmlFor="job-file">
                <FileUp size={17} /> Upload a job description
                <input
                  id="job-file"
                  type="file"
                  accept=".pdf,.docx,.txt"
                  disabled={busy}
                  onChange={(e) => chooseFile(e.target.files?.[0] || null)}
                />
              </label>
              <span>PDF, DOCX or TXT · up to 5 MB</span>
            </div>
            {file && (
              <div className="selected-file">
                <Check size={17} />
                <span>{file.name}</span>
                <button
                  className="icon-button"
                  aria-label="Remove selected file"
                  type="button"
                  disabled={busy}
                  onClick={() => setFile(null)}
                >
                  <X size={15} />
                </button>
              </div>
            )}
          </section>
          <section className="panel">
            <h2 id="options-heading">Interview options</h2>
            <fieldset disabled={busy}>
              <legend>Interview language</legend>
              <div className="choice-row">
                {(
                  [
                    ['en-HK', 'English'],
                    ['zh-HK', '廣東話'],
                  ] as const
                ).map(([value, label]) => (
                  <label
                    className={`choice-card ${language === value ? 'selected' : ''}`}
                    key={value}
                  >
                    <input
                      type="radio"
                      name="language"
                      value={value}
                      checked={language === value}
                      onChange={() => setLanguage(value)}
                    />
                    <strong>{label}</strong>
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="two-columns">
              <div>
                <label htmlFor="difficulty">Difficulty</label>
                <select
                  id="difficulty"
                  value={difficulty}
                  disabled={busy}
                  onChange={(e) => setDifficulty(e.target.value)}
                >
                  <option value="foundation">Foundation</option>
                  <option value="standard">Standard</option>
                  <option value="stretch">Stretch</option>
                </select>
              </div>
              <div>
                <label htmlFor="questions">Number of questions</label>
                <select
                  id="questions"
                  value={questions}
                  disabled={busy}
                  onChange={(e) => setQuestions(Number(e.target.value))}
                >
                  <option value={3}>3 questions</option>
                  <option value={5}>5 questions</option>
                  <option value={8}>8 questions</option>
                </select>
              </div>
            </div>
            <AppearanceSelector
              value={interviewer}
              disabled={busy}
              onChange={(id) => {
                setInterviewer(id);
                saveInterviewerPreference(id);
              }}
            />
          </section>
          {preparation && (
            <StartupProgress
              stage={preparation.stage}
              startedAt={preparation.startedAt}
              uploaded={!!file}
            />
          )}
          {error && <ErrorNotice message={error} onDismiss={() => setError('')} />}
          <div className="setup-start">
            <button className="button primary" type="submit" disabled={!valid || busy}>
              {busy ? 'Preparing your interview…' : 'Start my interview'}
              <ArrowRight size={18} />
            </button>
          </div>
        </div>
        <aside className="setup-aside" aria-labelledby="configuration-heading">
          <section className="panel configuration-panel">
            <h2 id="configuration-heading">Configuration status</h2>
            <dl className="configuration-summary">
              <div>
                <dt>Job description</dt>
                <dd>
                  {jobReady ? (file ? `Ready · ${file.name}` : 'Ready · pasted text') : 'Missing'}
                </dd>
              </div>
              <div>
                <dt>Language</dt>
                <dd>{language === 'zh-HK' ? '廣東話' : 'English'}</dd>
              </div>
              <div>
                <dt>Difficulty</dt>
                <dd>{difficulty[0].toUpperCase() + difficulty.slice(1)}</dd>
              </div>
              <div>
                <dt>Questions</dt>
                <dd>{questions}</dd>
              </div>
              <div>
                <dt>Interviewer</dt>
                <dd>{getInterviewer(interviewer).name}</dd>
              </div>
            </dl>
            <p className={`configuration-prompt ${jobReady ? 'ready' : ''}`} role="status">
              {busy
                ? 'Preparing your interview…'
                : jobReady
                  ? 'Ready to start.'
                  : 'Add a job description to start your interview.'}
            </p>
            <div className="configuration-services">
              <h3>Server readiness</h3>
              {healthUnavailable ? (
                <p className="field-help">
                  Server status is unavailable. Check the app service if starting fails.
                </p>
              ) : !health ? (
                <p className="field-help" role="status">
                  Checking services…
                </p>
              ) : (
                <dl className="configuration-summary">
                  <div>
                    <dt>Database</dt>
                    <dd>{health.database}</dd>
                  </div>
                  <div>
                    <dt>Interview coach</dt>
                    <dd>{health.provider === 'demo' ? 'Scripted demo' : health.llm}</dd>
                  </div>
                  <div>
                    <dt>Transcription</dt>
                    <dd>{health.speech}</dd>
                  </div>
                  <div>
                    <dt>Retrieval</dt>
                    <dd>{health.retrieval}</dd>
                  </div>
                </dl>
              )}
              <a className="text-button" href="#/settings">
                Inference settings <ArrowUpRight size={15} />
              </a>
            </div>
          </section>
        </aside>
      </form>
    </>
  );
}
