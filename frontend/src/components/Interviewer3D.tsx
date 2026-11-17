import { Eye, EyeOff } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { getInterviewer } from '../lib/interviewers';
import type { InterviewerId } from '../lib/interviewers';
import './Interviewer3D.css';

type Props = { interviewer: InterviewerId; state: string; speaking: boolean; speechCue: number };

export function Interviewer3D({ interviewer, state, speaking, speechCue }: Props) {
  const face = getInterviewer(interviewer);
  const host = useRef<HTMLDivElement>(null);
  const [hidden, setHidden] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);
  const [status, setStatus] = useState<'loading' | 'ready' | 'fallback'>('loading');
  const [reduced, setReduced] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );
  const current = useRef({ state, speaking, speechCue, reduced });
  useEffect(() => {
    current.current = { state, speaking, speechCue, reduced };
  }, [state, speaking, speechCue, reduced]);
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    if (!host.current || hidden) return;
    const element = host.current;
    const abort = new AbortController();
    let dispose: (() => void) | undefined;
    let closed = false;
    let failed = false;
    void import('../lib/portraitScene')
      .then(({ createPortraitScene }) => {
        if (closed) return;
        return createPortraitScene(
          element,
          face.src,
          `/interviewers/${face.id}.mesh.json`,
          () => current.current,
          abort.signal,
          () => {
            failed = true;
            if (!closed) {
              setStatus('fallback');
              abort.abort();
              dispose?.();
            }
          },
        );
      })
      .then((cleanup) => {
        if (closed || failed) {
          cleanup?.();
          return;
        }
        dispose = cleanup;
        if (!failed) setStatus('ready');
      })
      .catch(() => {
        if (!closed) setStatus('fallback');
      });
    return () => {
      closed = true;
      abort.abort();
      dispose?.();
    };
  }, [face.id, face.src, hidden]);
  return (
    <>
      <div className="interviewer-heading">
        <span className="portrait-name">
          {face.name}
          <small>Interviewer</small>
        </span>
        <button
          className="icon-button"
          aria-label={hidden ? 'Show interviewer' : 'Hide interviewer'}
          aria-pressed={hidden}
          onClick={() => {
            setHidden((value) => !value);
            setStatus('loading');
          }}
        >
          {hidden ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
      <div className="portrait-frame interviewer-3d-frame">
        {hidden ? (
          <div className="portrait-fallback">Interviewer hidden</div>
        ) : (
          <>
            {status !== 'ready' &&
              (imageFailed ? (
                <div className="portrait-fallback">{face.name} · Image unavailable</div>
              ) : (
                <img
                  src={face.src}
                  width={1086}
                  height={1448}
                  alt={`${face.name}, interviewer portrait`}
                  onError={() => setImageFailed(true)}
                />
              ))}
            <div
              ref={host}
              className="interviewer-3d-canvas"
              role="img"
              aria-hidden={status !== 'ready'}
              aria-label={`${face.name}, 3D interviewer${speaking ? ' speaking' : ''}`}
            />
            {status === 'loading' && (
              <div className="interviewer-loading" role="status">
                Loading interviewer…
              </div>
            )}
          </>
        )}
      </div>
      {!hidden && status === 'fallback' && (
        <p className="interviewer-fallback-notice" role="status">
          3D view unavailable. You can continue with the portrait.
        </p>
      )}
    </>
  );
}
