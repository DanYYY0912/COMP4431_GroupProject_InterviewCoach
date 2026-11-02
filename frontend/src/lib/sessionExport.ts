import { api } from './api';
import { exportJson } from './format';

export async function loadSessionExport(id: string) {
  const session = await api.session(id);
  const report = session.state === 'completed' ? await api.report(id) : null;
  if (report && report.session_id !== session.id) {
    throw new Error('The debrief does not match this session. Reload before exporting.');
  }
  return {
    format: 'voxprep.session' as const,
    version: 1 as const,
    exported_at: new Date().toISOString(),
    session,
    report,
  };
}

export async function downloadSession(id: string) {
  const content = await loadSessionExport(id);
  exportJson(content, `voxprep-session-${id}.json`);
}
