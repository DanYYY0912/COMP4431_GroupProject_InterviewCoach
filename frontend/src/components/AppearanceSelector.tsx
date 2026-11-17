import { useState } from 'react';
import { interviewers } from '../lib/interviewers';
import type { InterviewerId } from '../lib/interviewers';
import './SetupPreparation.css';

function AppearancePhoto({ src }: { src: string }) {
  const [failed, setFailed] = useState(false);
  return failed ? (
    <span className="appearance-image-unavailable">Preview unavailable</span>
  ) : (
    <img src={src} alt="" width={1086} height={1448} onError={() => setFailed(true)} />
  );
}

export function AppearanceSelector({
  value,
  onChange,
  disabled = false,
}: {
  value: InterviewerId;
  onChange: (id: InterviewerId) => void;
  disabled?: boolean;
}) {
  return (
    <fieldset
      className="appearance-selector"
      disabled={disabled}
      aria-describedby="appearance-help"
    >
      <legend>Interviewer appearance</legend>
      <div className="appearance-options">
        {interviewers.map((interviewer) => (
          <label
            className={`appearance-option ${value === interviewer.id ? 'selected' : ''}`}
            key={interviewer.id}
          >
            <span className="appearance-image">
              <AppearancePhoto src={interviewer.src} />
            </span>
            <span className="appearance-option-label">
              <input
                type="radio"
                name="interviewer"
                value={interviewer.id}
                checked={value === interviewer.id}
                onChange={() => onChange(interviewer.id)}
              />
              <span>{interviewer.name}</span>
            </span>
          </label>
        ))}
      </div>
      <p id="appearance-help" className="field-help">
        This interviewer is saved with the session.
      </p>
    </fieldset>
  );
}
