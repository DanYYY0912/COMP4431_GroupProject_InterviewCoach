import { Eye, EyeOff } from 'lucide-react';
import { useState } from 'react';

const faces = [
  { id: 'alex', name: 'Alex', src: '/interviewers/alex.png' },
  { id: 'jamie', name: 'Jamie', src: '/interviewers/jamie.png' },
  { id: 'sam', name: 'Sam', src: '/interviewers/sam.png' },
] as const;
type Face = (typeof faces)[number];
type FaceId = Face['id'];
const storageKey = 'voxprep.interviewer';

function savedFace(): FaceId {
  try {
    const saved = localStorage.getItem(storageKey);
    return faces.find((face) => face.id === saved)?.id || 'alex';
  } catch {
    return 'alex';
  }
}

function PortraitPhoto({ face, thumbnail = false }: { face: Face; thumbnail?: boolean }) {
  const [failed, setFailed] = useState(false);
  if (failed)
    return thumbnail ? (
      <span className="portrait-thumbnail-fallback" aria-hidden="true">
        {face.name[0]}
      </span>
    ) : (
      <div className="portrait-fallback" role="status">
        <strong>{face.name}</strong>
        <span>Portrait unavailable</span>
      </div>
    );
  return (
    <img
      src={face.src}
      alt={thumbnail ? '' : `${face.name}, interviewer portrait`}
      width={1086}
      height={1448}
      decoding="async"
      onError={() => setFailed(true)}
    />
  );
}

export function InterviewerPortrait() {
  const [selected, setSelected] = useState<FaceId>(savedFace);
  const [hidden, setHidden] = useState(false);
  const face = faces.find((item) => item.id === selected) || faces[0];
  function choose(id: FaceId) {
    setSelected(id);
    try {
      localStorage.setItem(storageKey, id);
    } catch {
      // The current selection remains usable when browser storage is unavailable.
    }
  }
  return (
    <>
      <div className="interviewer-heading">
        <span className="portrait-name">
          {face.name}
          <small>Interviewer</small>
        </span>
        <button
          className="icon-button"
          aria-label={hidden ? 'Show interviewer portrait' : 'Hide interviewer portrait'}
          aria-pressed={hidden}
          onClick={() => setHidden((value) => !value)}
        >
          {hidden ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
      <div className={`portrait-frame ${hidden ? 'is-hidden' : ''}`}>
        {hidden ? (
          <div className="portrait-fallback">
            <span>Portrait hidden</span>
          </div>
        ) : (
          <PortraitPhoto key={selected} face={face} />
        )}
      </div>
      <fieldset className="portrait-choices" aria-describedby="portrait-choice-help">
        <legend>Interviewer appearance</legend>
        <div className="portrait-choice-row">
          {faces.map((item) => (
            <label
              className={`portrait-choice ${selected === item.id ? 'selected' : ''}`}
              key={item.id}
            >
              <input
                type="radio"
                name="interviewer-appearance"
                value={item.id}
                checked={selected === item.id}
                onChange={() => choose(item.id)}
              />
              <span className="portrait-thumbnail">
                <PortraitPhoto face={item} thumbnail />
              </span>
              <span>{item.name}</span>
            </label>
          ))}
        </div>
        <p id="portrait-choice-help">Appearance only; interview settings stay the same.</p>
      </fieldset>
    </>
  );
}
