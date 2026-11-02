import { useCallback, useEffect, useState } from 'react';
import {
  ArrowUpRight,
  AudioLines,
  FlaskConical,
  LayoutDashboard,
  Plus,
  ShieldCheck,
} from 'lucide-react';
import { Dashboard } from './pages/Dashboard';
import { Setup } from './pages/Setup';
import { Interview } from './pages/Interview';
import { Report } from './pages/Report';
import { Methodology } from './pages/Methodology';

function routePath() {
  return window.location.hash.replace(/^#/, '') || '/';
}
export default function App() {
  const [path, setPath] = useState(routePath);
  const [speechConsent, setSpeechConsent] = useState(false);
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
  const section =
    page === 'setup'
      ? 'New practice'
      : page === 'interview'
        ? 'Practice interview'
        : page === 'report'
          ? 'Session debrief'
          : page === 'methodology'
            ? 'Methodology'
            : 'Overview';
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
            <small>FIND YOUR VOICE.</small>
          </span>
        </a>
        <div className="nav-label">YOUR WORKSPACE</div>
        <nav aria-label="Main navigation">
          <a className={!page ? 'active' : ''} href="#/" aria-current={!page ? 'page' : undefined}>
            <LayoutDashboard size={19} /> Overview
          </a>
          <a
            className={['setup', 'interview'].includes(page) ? 'active' : ''}
            href="#/setup"
            aria-current={['setup', 'interview'].includes(page) ? 'page' : undefined}
          >
            <AudioLines size={19} /> Practice interview
          </a>
          <a
            className={page === 'methodology' ? 'active' : ''}
            href="#/methodology"
            aria-current={page === 'methodology' ? 'page' : undefined}
          >
            <FlaskConical size={19} /> Methodology
          </a>
        </nav>
        <div className="sidebar-bottom">
          <div className="privacy-note">
            <ShieldCheck size={20} />
            <strong>A space to grow.</strong>
            <p>Your practice stays on this computer. Your next step is yours.</p>
          </div>
          <div className="sidebar-footer">
            <span className="status-dot" /> LOCAL-FIRST PRACTICE
            <span className="version">v0.1</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <span>My workspace</span>
            <span className="breadcrumb-divider">/</span>
            <strong>{section}</strong>
          </div>
          <a className="topbar-action" href="#/setup">
            <Plus size={16} /> New practice <ArrowUpRight size={15} />
          </a>
        </header>
        <main id="main-content" tabIndex={-1}>
          {page === 'setup' ? (
            <Setup navigate={navigate} onSpeechConsent={setSpeechConsent} />
          ) : page === 'interview' && id ? (
            <Interview
              key={id}
              id={decodeURIComponent(id)}
              navigate={navigate}
              speechConsent={speechConsent}
              onSpeechConsent={setSpeechConsent}
            />
          ) : page === 'report' && id ? (
            <Report key={id} id={decodeURIComponent(id)} navigate={navigate} />
          ) : page === 'methodology' ? (
            <Methodology />
          ) : (
            <Dashboard navigate={navigate} />
          )}
        </main>
        <footer className="page-footer">
          <span>Made for your next opportunity.</span>
          <span>
            VoxPrep HK <span>·</span> COMP4431
          </span>
        </footer>
      </div>
    </div>
  );
}
