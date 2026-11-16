import {
  ArrowLeft,
  ArrowRight,
  Check,
  FileUp,
  Mic,
  ShieldCheck,
  Sparkles,
  Volume2,
  X,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { api, errorMessage } from '../lib/api';
import { pickVoice } from '../lib/audio';
import type { Health, Language } from '../lib/types';
import { ErrorNotice, Preflight } from '../components/Common';

const sample = `Graduate Software Engineer — Hong Kong\nJoin a product team building reliable web applications for local businesses.\nResponsibilities: build Python REST APIs and React interfaces; design SQL database queries; write automated tests; debug production issues with the team; communicate trade-offs clearly in English and Cantonese.\nRequirements: a degree in computer science or a related subject, practical knowledge of Python or JavaScript, Git and data structures, teamwork, curiosity, and evidence of a project where you solved a technical problem.\nWe value thoughtful problem solving, clear communication, and measurable improvements to software quality.`;

export function Setup({
  navigate,
  onSpeechConsent,
}: {
  navigate: (path: string) => void;
  onSpeechConsent: (value: boolean) => void;
}) {
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [language, setLanguage] = useState<Language>('en-HK');
  const [difficulty, setDifficulty] = useState('standard');
  const [questions, setQuestions] = useState(5);
  const [consent, setConsent] = useState(false);
  const [speech, setSpeech] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [health, setHealth] = useState<Health | null>(null);
  const [micStatus, setMicStatus] = useState('');
  const [retryNotice, setRetryNotice] = useState('');
  const [micEcho, setMicEcho] = useState('');
  const [speakerStatus, setSpeakerStatus] = useState('');
  useEffect(() => () => {
    if (micEcho) URL.revokeObjectURL(micEcho);
  }, [micEcho]);
  useEffect(() => {
    // Deep link from the printed PDF: #/setup?retry=1&from=<session>&lang=<language>
    const query = window.location.hash.split('?')[1];
    if (!query) return;
    const params = new URLSearchParams(query);
    if (params.get('retry') !== '1') return;
    const lang = params.get('lang');
    if (lang === 'zh-HK' || lang === 'en-HK') setLanguage(lang);
    setRetryNotice(
      'Continuing from your debrief. Paste the same job description again (or upload the file) and start the next round.',
    );
  }, []);
  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() =>
        setError('The local service is unavailable. Start the API, then reload this page.'),
      );
  }, []);
  async function start(event: FormEvent) {
    event.preventDefault();
    if (!consent || busy) return;
    setBusy(true);
    setError('');
    try {
      const profile = await api.profile(text, file);
      const session = await api.create(profile.id, language, difficulty, questions);
      onSpeechConsent(speech);
      navigate(`/interview/${session.id}`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function checkMic() {
    // Record three seconds and play it straight back: a permission prompt alone does not prove
    // the microphone actually captures sound.
    let stream: MediaStream | null = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (typeof MediaRecorder === 'undefined') {
        setMicStatus('This browser cannot record audio. Typing still works.');
        return;
      }
      setMicStatus('Recording three seconds — say something…');
      const recorder = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      const stopped = new Promise<void>((resolve) => {
        recorder.onstop = () => resolve();
      });
      recorder.start();
      await new Promise((resolve) => setTimeout(resolve, 3000));
      recorder.stop();
      await stopped;
      const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
      if (micEcho) URL.revokeObjectURL(micEcho);
      setMicEcho(URL.createObjectURL(blob));
      setMicStatus(
        `Recorded ${Math.max(1, Math.round(blob.size / 1024))} KB. Play it back below — if you hear yourself, the microphone works. Nothing is uploaded.`,
      );
    } catch {
      setMicStatus('Microphone unavailable. You can type every answer.');
    } finally {
      stream?.getTracks().forEach((track) => track.stop());
    }
  }
  function checkSpeaker() {
    if (!('speechSynthesis' in window)) {
      setSpeakerStatus('Browser speech is unavailable. Captions remain available.');
      return;
    }
    speechSynthesis.cancel();
    const voice = pickVoice(language);
    if (!voice) {
      setSpeakerStatus('No system voice found. Captions remain available.');
      return;
    }
    const utterance = new SpeechSynthesisUtterance(
      language === 'zh-HK' ? '你好，準備好練習未？' : 'Hello. Let’s practise your next interview.',
    );
    utterance.voice = voice;
    utterance.lang = voice.lang;
    speechSynthesis.speak(utterance);
    setSpeakerStatus(`Playing the speaker test with “${voice.name}” (${voice.lang}).`);
  }
  function chooseFile(selected: File | null) {
    if (selected && selected.size > 5 * 1024 * 1024) {
      setError('Choose a document no larger than 5 MB.');
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
      <button className="back-link" onClick={() => navigate('/')}>
        <ArrowLeft size={16} /> Back to your practice space
      </button>
      <div className="page-heading compact">
        <div>
          <p className="eyebrow">LET’S MAKE IT RELEVANT</p>
          <h1>Set the scene.</h1>
          <p className="lead">A real role. Your language. A little room to grow.</p>
        </div>
        <span className="step-marker">
          01 <span>/ 03</span>
        </span>
      </div>
      <form className="setup-grid" onSubmit={start}>
        <div className="setup-main">
          <section className="panel">
            <div className="section-heading">
              <h2>
                <span className="number-label">1</span> Bring the opportunity
              </h2>
              <button
                className="text-button"
                type="button"
                onClick={() => {
                  setText(sample);
                  setFile(null);
                }}
              >
                <Sparkles size={15} /> Try a sample role
              </button>
            </div>
            <label htmlFor="job-text">Job description</label>
            <p className="field-help" id="job-help">
              Paste the role you’re applying for, or upload a text-based document.
            </p>
            <textarea
              id="job-text"
              aria-describedby="job-help"
              rows={9}
              value={text}
              disabled={!!file}
              onChange={(e) => setText(e.target.value)}
              placeholder="Graduate software engineer…\nResponsibilities, skills, and what the team is looking for."
              maxLength={50000}
            />
            <div className="upload-row">
              <label className="upload-button" htmlFor="job-file">
                <FileUp size={17} /> Upload a job description
                <input
                  id="job-file"
                  type="file"
                  accept=".pdf,.docx,.txt"
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
                  onClick={() => setFile(null)}
                >
                  <X size={15} />
                </button>
              </div>
            )}
          </section>
          <section className="panel">
            <h2>
              <span className="number-label">2</span> Make it yours
            </h2>
            <fieldset>
              <legend>Interview language</legend>
              <div className="choice-row">
                {(
                  [
                    ['en-HK', 'English', 'Find the words that work.'],
                    ['zh-HK', '廣東話', '用你熟悉嘅語言，講好你嘅故事。'],
                  ] as const
                ).map(([value, label, note]) => (
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
                    <span>{note}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="two-columns">
              <div>
                <label htmlFor="difficulty">Challenge level</label>
                <select
                  id="difficulty"
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                >
                  <option value="foundation">Foundation · build confidence</option>
                  <option value="standard">Standard · find your rhythm</option>
                  <option value="stretch">Stretch · go a little deeper</option>
                </select>
              </div>
              <div>
                <label htmlFor="questions">Number of questions</label>
                <select
                  id="questions"
                  value={questions}
                  onChange={(e) => setQuestions(Number(e.target.value))}
                >
                  <option value={3}>3 questions · a quick practice</option>
                  <option value={5}>5 questions · a focused session</option>
                  <option value={8}>8 questions · a deeper dive</option>
                </select>
              </div>
            </div>
          </section>
        </div>
        <aside className="setup-aside">
          <section className="panel readiness-panel">
            <h2>A moment to get ready</h2>
            <Preflight health={health} />
            <div className="device-checks">
              <button
                type="button"
                className="button secondary small"
                onClick={() => void checkMic()}
              >
                <Mic size={16} /> Test microphone
              </button>
              <button type="button" className="button secondary small" onClick={checkSpeaker}>
                <Volume2 size={16} /> Test speaker
              </button>
            </div>
            {micStatus && (
              <p className="field-help" role="status">
                {micStatus}
              </p>
            )}
            {micEcho && (
              <audio
                controls
                autoPlay
                src={micEcho}
                aria-label="Your recorded microphone test"
                style={{ width: '100%', marginTop: '0.5rem' }}
              />
            )}
            {speakerStatus && (
              <p className="field-help" role="status">
                {speakerStatus}
              </p>
            )}
            <div className="consent-section">
              <ShieldCheck size={23} />
              <h3>Your story stays yours.</h3>
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  required
                />
                <span>
                  Save this session and transcript on this computer. I can export or delete it
                  later.
                </span>
              </label>
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={speech}
                  onChange={(e) => setSpeech(e.target.checked)}
                />
                <span>
                  Enable Azure voice. Audio and interviewer text may be sent to Microsoft Speech.
                  This is optional.
                </span>
              </label>
              <p className="field-help">
                With voice off, you can type every answer. The coach never rates your appearance,
                accent, or employability.
              </p>
            </div>
            <button
              className="button primary full"
              type="submit"
              disabled={busy || !consent || (!file && text.trim().length < 40)}
            >
              {busy ? 'Preparing your interview…' : 'Start my interview'} <ArrowRight size={18} />
            </button>
          </section>
          {retryNotice && (
            <p className="field-help" role="status" style={{ marginBottom: '0.75rem' }}>
              {retryNotice}
            </p>
          )}
          {error && <ErrorNotice message={error} onDismiss={() => setError('')} />}
        </aside>
      </form>
    </>
  );
}
