import { lazy, Suspense, useEffect, useEffectEvent, useRef, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  AudioLines,
  ChevronRight,
  Clock3,
  Eye,
  EyeOff,
  Keyboard,
  Mic,
  Pause,
  Play,
  RotateCcw,
  Send,
  SkipForward,
  Square,
  Volume2,
} from 'lucide-react';
import { api, errorMessage } from '../lib/api';
import { playQuestion, recordMicrophone } from '../lib/audio';
import type { RecordedAnswer } from '../lib/audio';
import type { Language } from '../lib/types';
import { formatDuration } from '../lib/format';
import { useLiveSession } from '../lib/useLiveSession';
import { ErrorNotice, Loading, ProviderBadge, Sources } from '../components/Common';

const Avatar = lazy(() => import('../components/Avatar'));
const statusLabels: Record<string, string> = {
  ready: 'Ready when you are',
  listening: 'Listening to your story',
  initializing: 'Waiting for microphone permission',
  transcribing: 'Preparing your transcript',
  thinking: 'Thinking about your answer',
  speaking: 'Your interviewer is speaking',
  paused: 'Take a breath. We’re paused.',
  completed: 'Practice complete',
};

export function Interview({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const live = useLiveSession(id);
  const { session, busy } = live;
  const [chosenLanguage, setChosenLanguage] = useState<Language | null>(null);
  const answerLanguage = chosenLanguage || session?.language || 'en-HK';
  const [transcript, setTranscript] = useState('');
  const [corrected, setCorrected] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [started, setStarted] = useState(false);
  const [speechState, setSpeechState] = useState('');
  const [mouth, setMouth] = useState(0);
  const [level, setLevel] = useState(0);
  const [notice, setNotice] = useState('');
  const [avatarOff, setAvatarOff] = useState(false);
  const [metrics, setMetrics] = useState<RecordedAnswer | null>(null);
  const recorder = useRef<Awaited<ReturnType<typeof recordMicrophone>> | null>(null);
  const playback = useRef<(() => void) | null>(null);
  const transcriptionAbort = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const turn = session?.turns[session.turns.length - 1];
  const paused = session?.state === 'paused';
  const displayState = paused ? 'paused' : speechState || (busy ? 'thinking' : live.state);
  const recording = speechState === 'listening';
  const audioBusy = recording || speechState === 'transcribing' || speechState === 'initializing';
  useEffect(() => {
    if (session?.state === 'completed') navigate(`/report/${id}`);
  }, [session?.state, id, navigate]);
  useEffect(() => {
    setTranscript('');
    setCorrected(false);
    setMetrics(null);
    setElapsed(0);
    setStarted(false);
    playback.current?.();
  }, [turn?.id]);
  useEffect(() => {
    if (!started || paused || busy || speechState === 'speaking' || speechState === 'transcribing')
      return;
    const timer = setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [started, paused, busy, speechState]);
  useEffect(
    () => () => {
      generation.current++;
      transcriptionAbort.current?.abort();
      playback.current?.();
      void recorder.current?.stop();
    },
    [],
  );
  function stopSpeaking() {
    playback.current?.();
    playback.current = null;
    setMouth(0);
    if (speechState === 'speaking') setSpeechState('');
  }
  function speak() {
    if (!turn || !session) return;
    stopSpeaking();
    setNotice('');
    playback.current = playQuestion(turn.question.interviewer_text, session.language, {
      onStart: () => setSpeechState('speaking'),
      onMouth: setMouth,
      onEnd: () => setSpeechState(''),
      onNotice: setNotice,
    });
  }
  async function beginRecording() {
    if (!session || paused || busy || audioBusy) return;
    stopSpeaking();
    const run = ++generation.current;
    setNotice('');
    setSpeechState('initializing');
    try {
      const capture = await recordMicrophone(setLevel);
      if (run !== generation.current) {
        await capture.stop();
        return;
      }
      recorder.current = capture;
      setTranscript('');
      setCorrected(false);
      setMetrics(null);
      setStarted(true);
      setElapsed(0);
      setSpeechState('listening');
      setNotice('Recording. Finish recording to transcribe your answer.');
    } catch {
      if (run !== generation.current) return;
      setSpeechState('');
      setNotice('Microphone access is unavailable. Type your answer below to continue.');
    }
  }
  async function finishRecording(discard = false) {
    const capture = recorder.current;
    if (!capture) return;
    recorder.current = null;
    const run = ++generation.current;
    setSpeechState(discard ? '' : 'transcribing');
    try {
      const result = await capture.stop();
      if (run !== generation.current || discard) return;
      setMetrics(result);
      setElapsed(Math.round(result.duration));
      const abort = new AbortController();
      transcriptionAbort.current = abort;
      const transcription = await api.transcribe(result.blob, answerLanguage, abort.signal);
      if (run !== generation.current) return;
      setTranscript(transcription.text);
      setNotice('Your transcript is ready. Please check the wording before sending.');
    } catch (e) {
      if (run === generation.current)
        setNotice(`${errorMessage(e)} You can type your answer below.`);
    } finally {
      if (run === generation.current) {
        transcriptionAbort.current = null;
        setSpeechState('');
      }
    }
  }
  const stopAtLimit = useEffectEvent(() => {
    void finishRecording();
  });
  useEffect(() => {
    if (!recording) return;
    const timer = setTimeout(stopAtLimit, 300000);
    return () => clearTimeout(timer);
  }, [recording]);
  async function control(action: 'pause' | 'resume' | 'skip' | 'retry' | 'end' | 'cancel') {
    generation.current++;
    transcriptionAbort.current?.abort();
    transcriptionAbort.current = null;
    setSpeechState('');
    stopSpeaking();
    if (recorder.current) await finishRecording(true);
    await live.control(action);
  }
  async function submit() {
    if (!session || !transcript.trim() || paused || busy || audioBusy) return;
    stopSpeaking();
    await live.answer({
      transcript: transcript.trim(),
      language: answerLanguage,
      turn_id: turn?.id,
      elapsed_seconds: Math.max(1, metrics?.duration || elapsed),
      corrected,
      ...(metrics
        ? {
            speech_metrics: {
              pause_count: metrics.pauseCount,
              silence_seconds: metrics.silenceSeconds,
            },
          }
        : {}),
    });
  }
  if (!session) return live.error ? <ErrorNotice message={live.error} /> : <Loading />;
  const question = turn?.question;
  const progressed = Math.max(0, session.current_question - 1);
  return (
    <>
      <div className="interview-top">
        <button className="back-link" onClick={() => navigate('/history')}>
          <ArrowLeft size={16} /> {transcript.trim() ? 'Leave & discard draft' : 'Leave practice'}
        </button>
        <ProviderBadge provider={session.provider} />
      </div>
      <div className="page-heading compact">
        <div>
          <p className="eyebrow">YOUR PRACTICE, IN PROGRESS</p>
          <h1 className="interview-title">{session.role_title}</h1>
          <p className="lead">
            {session.language === 'zh-HK'
              ? '慢慢嚟。呢度係俾你練習嘅空間。'
              : 'Take your time. This is a space to practise.'}
          </p>
        </div>
        <span className="step-marker">
          02 <span>/ 03</span>
        </span>
      </div>
      {live.error && <ErrorNotice message={live.error} onDismiss={() => live.setError('')} />}
      <div className="interview-grid">
        <section className="interviewer-panel" aria-label="Interviewer">
          <div className="interviewer-heading">
            <span className="pill neutral">
              <span className="status-dot" /> VOX · YOUR PRACTICE COACH
            </span>
            <button
              className="icon-button"
              aria-label={avatarOff ? 'Enable animated avatar' : 'Disable animated avatar'}
              aria-pressed={avatarOff}
              onClick={() => setAvatarOff((value) => !value)}
            >
              {avatarOff ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
          <div className="avatar-stage">
            <span className="avatar-ring" />
            <Suspense
              fallback={
                <div className="portrait-placeholder">
                  <AudioLines size={58} />
                </div>
              }
            >
              <Avatar mouth={mouth} state={displayState} disabled={avatarOff} />
            </Suspense>
          </div>
          <div className="coach-state" role="status">
            <span className={`status-dot ${displayState === 'listening' ? 'pulse' : ''}`} />
            {statusLabels[displayState] || 'Ready when you are'}
          </div>
          <div className="waveform" role="img" aria-label="Microphone activity">
            {Array.from({ length: 32 }, (_, i) => (
              <span key={i} style={{ height: `${4 + level * (8 + ((i * 13) % 29))}px` }} />
            ))}
          </div>
          <div className="interviewer-actions">
            <button
              className="button small secondary"
              disabled={busy || audioBusy || paused}
              onClick={speak}
            >
              <Volume2 size={16} /> Read question
            </button>
            {speechState === 'speaking' && (
              <button className="button small secondary" onClick={stopSpeaking}>
                <Square size={14} /> Stop audio
              </button>
            )}
          </div>
          <p className="avatar-note">Original 3D interviewer · captions always available</p>
        </section>
        <div className="answer-column">
          <div className="question-progress">
            <span>
              Question {Math.min(session.current_question, session.question_count)}{' '}
              <span>of {session.question_count}</span>
            </span>
            <span>
              <Clock3 size={15} /> {formatDuration(elapsed)}
            </span>
          </div>
          <div
            className="progress-track"
            role="progressbar"
            aria-label="Interview progress"
            aria-valuenow={progressed}
            aria-valuemin={0}
            aria-valuemax={session.question_count}
          >
            <span style={{ width: `${(progressed / session.question_count) * 100}%` }} />
          </div>
          <section className="question-card">
            <div className="question-meta">
              <span className="eyebrow">
                {question?.question_type === 'follow_up'
                  ? 'LET’S GO A LITTLE DEEPER'
                  : 'YOUR NEXT QUESTION'}
              </span>
              <span>{session.language === 'zh-HK' ? '廣東話' : 'English'}</span>
            </div>
            <h2 lang={session.language === 'zh-HK' ? 'zh-HK' : 'en'}>
              {question?.interviewer_text}
            </h2>
            {question?.adaptive_follow_up_reason && (
              <p className="follow-up-reason">
                <ChevronRight size={16} /> {question.adaptive_follow_up_reason}
              </p>
            )}
            <div className="competency-tags">
              {question?.targeted_competencies.map((c) => (
                <span key={c}>{c}</span>
              ))}
            </div>
            {question && <Sources citations={question.citations} />}
          </section>
          <section className="answer-panel">
            <div className="answer-label">
              <label htmlFor="answer">
                {session.language === 'zh-HK' ? 'Your answer · 你嘅回答' : 'Your answer'}
              </label>
              <span>
                <Keyboard size={14} /> Type or speak
              </span>
            </div>
            <div className="answer-language">
              <label htmlFor="answer-language">Answer language</label>
              <select
                id="answer-language"
                value={answerLanguage}
                disabled={paused || busy || audioBusy}
                onChange={(event) => setChosenLanguage(event.target.value as Language)}
              >
                <option value="en-HK">English</option>
                <option value="zh-HK">廣東話</option>
              </select>
            </div>
            <textarea
              id="answer"
              rows={6}
              placeholder={
                answerLanguage === 'zh-HK'
                  ? '例如：喺大學小組專題入面，我負責…'
                  : 'Think of a specific experience. What happened, what did you do, and what changed?'
              }
              value={transcript}
              onFocus={() => setStarted(true)}
              onChange={(e) => {
                setTranscript(e.target.value);
                setCorrected(true);
                setStarted(true);
              }}
              readOnly={recording}
              disabled={paused || busy || speechState === 'transcribing'}
              maxLength={12000}
              aria-describedby="answer-hint"
            />
            <div className="answer-hint" id="answer-hint">
              <span>Editable captions. Only the answer you send is saved.</span>
              <span>{transcript.length.toLocaleString()}/12,000</span>
            </div>
            {notice && (
              <p className="speech-notice" role="status">
                {notice}
              </p>
            )}
            <div className="answer-actions">
              {recording ? (
                <button className="button recording" onClick={() => void finishRecording()}>
                  <Square size={16} /> Finish recording
                </button>
              ) : (
                <button
                  className="button secondary"
                  disabled={paused || busy || audioBusy}
                  onClick={() => void beginRecording()}
                >
                  <Mic size={17} /> {transcript ? 'Re-record answer' : 'Record answer'}
                </button>
              )}
              <button
                className="button primary"
                disabled={!transcript.trim() || paused || busy || audioBusy}
                onClick={() => void submit()}
              >
                {busy ? 'Thinking…' : 'Send answer'} <Send size={17} />
              </button>
            </div>
          </section>
          <div className="session-controls">
            {busy && (
              <button className="text-button" onClick={() => void control('cancel')}>
                <Square size={14} /> Stop thinking
              </button>
            )}
            <button
              className="text-button"
              onClick={() => void control(paused ? 'resume' : 'pause')}
            >
              {paused ? <Play size={15} /> : <Pause size={15} />}
              {paused ? 'Resume practice' : 'Pause'}
            </button>
            <button
              className="text-button"
              disabled={busy || paused || audioBusy}
              onClick={() => {
                setTranscript('');
                setMetrics(null);
                setElapsed(0);
                setStarted(false);
              }}
            >
              <RotateCcw size={15} /> Clear draft
            </button>
            <button
              className="text-button"
              disabled={busy || paused || audioBusy}
              onClick={() => void control('skip')}
            >
              <SkipForward size={15} /> Skip question
            </button>
            <button
              className="text-button finish"
              disabled={recording}
              onClick={() => void control('end')}
            >
              Finish & review <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
