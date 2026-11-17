import { useCallback, useEffect, useState } from 'react';
import { AudioLines, History as HistoryIcon, SlidersHorizontal } from 'lucide-react';
import { History } from './pages/History';
import { Setup } from './pages/Setup';
import { Interview } from './pages/Interview';
import { Report } from './pages/Report';
import { InferenceSettings } from './pages/InferenceSettings';

function routePath() {
  return window.location.hash.replace(/^#/, '') || '/';
}
export default function App() {
  const [path, setPath] = useState(routePath);
  const navigate = useCallback((next: string) => {
    window.location.hash = next;
  }, []);
  useEffect(() => {
    const listener = () => {
      setPath(routePath());
      window.scrollTo({ top: 0, behavior: 'instant' });
    };
    window.addEventListener('hashchange', listener);
    return () => window.removeEventListener('hashchange', listener);
  }, []);
  useEffect(() => {
    const title = document.querySelector<HTMLElement>('h1');
    title?.setAttribute('tabindex', '-1');
    title?.focus({ preventScroll: true });
  }, [path]);
  const [page, id] = path.slice(1).split('/');
  const isSettings = ['settings', 'methodology'].includes(page);
  const isPractice = !['history', 'report', 'settings', 'methodology'].includes(page);
  const section = isSettings
    ? 'Settings'
    : page === 'history'
      ? 'History'
      : page === 'report'
        ? 'Session debrief'
        : 'Practice interview';
  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById('main-content')?.focus();
        }}
      >
        Skip to main content
      </a>
      <aside className="sidebar">
        <a className="brand" href="#/" aria-label="VoxPrep HK home">
          <span className="brand-mark">
            v<span>.</span>
          </span>
          <span>
            VoxPrep<span className="brand-hk">HK</span>
          </span>
        </a>
        <nav aria-label="Main navigation">
          <a
            className={isPractice ? 'active' : ''}
            href="#/setup"
            aria-current={isPractice ? 'page' : undefined}
          >
            <AudioLines size={19} /> Practice interview
          </a>
          <a
            className={page === 'history' ? 'active' : ''}
            href="#/history"
            aria-current={page === 'history' ? 'page' : undefined}
          >
            <HistoryIcon size={19} /> History
          </a>
          <a
            className={isSettings ? 'active' : ''}
            href="#/settings"
            aria-current={isSettings ? 'page' : undefined}
          >
            <SlidersHorizontal size={19} /> Settings
          </a>
        </nav>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <strong>{section}</strong>
        </header>
        <main id="main-content" tabIndex={-1}>
          {page === 'interview' && id ? (
            <Interview key={id} id={decodeURIComponent(id)} navigate={navigate} />
          ) : page === 'report' && id ? (
            <Report key={id} id={decodeURIComponent(id)} navigate={navigate} />
          ) : isSettings ? (
            <InferenceSettings />
          ) : page === 'history' ? (
            <History navigate={navigate} />
          ) : (
            <Setup navigate={navigate} />
          )}
        </main>
      </div>
    </div>
  );
}
