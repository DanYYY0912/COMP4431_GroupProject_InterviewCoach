import { api } from './api';
import type { Report, Session } from './types';

/**
 * Printable session report.
 *
 * The PDF is produced by the browser's own "Save as PDF" from a purpose-built print document,
 * not by a server-side PDF library: the styling is then the app's own palette, the output stays
 * selectable text, and no extra dependency enters the backend.
 */

const PALETTE = {
  ink: '#203d34',
  teal: '#256456',
  cream: '#f6f4ed',
  gold: '#d8b779',
  muted: '#52645e',
  line: '#d9ddd6',
};

function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function paragraphs(text: string, className = ''): string {
  return String(text ?? '')
    .split(/\n{2,}/)
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => `<p class="${className}">${escapeHtml(chunk)}</p>`)
    .join('');
}

function strengthText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value && typeof value === 'object' && 'text' in value) return String((value as { text: string }).text);
  return '';
}

function metric(label: string, value: unknown, suffix = ''): string {
  const shown = value === null || value === undefined ? '—' : `${value}${suffix}`;
  return `<div class="metric"><span class="metric-value">${escapeHtml(shown)}</span><span class="metric-label">${escapeHtml(
    label,
  )}</span></div>`;
}

export function buildReportHtml(session: Session, report: Report | null, exportedAt = new Date()): string {
  const language = session.language === 'zh-HK' ? 'Cantonese (zh-HK)' : 'English (en-HK)';
  const date = exportedAt.toLocaleString('en-HK', { dateStyle: 'medium', timeStyle: 'short' });
  const answers = session.turns.filter((turn) => turn.answer);
  const provider = session.provider || 'unknown';

  const star = (report?.star ?? [])
    .map(
      (item) => `
        <tr class="${item.present ? 'present' : 'missing'}">
          <th>${escapeHtml(item.element)}</th>
          <td>${item.present ? '✓' : '—'}</td>
          <td class="evidence">${item.evidence ? `“${escapeHtml(item.evidence)}”` : '<span class="muted">No evidence quoted</span>'}</td>
          <td>${escapeHtml(item.coaching)}</td>
        </tr>`,
    )
    .join('');

  const competencies = (report?.competencies ?? [])
    .map(
      (item) => `
        <article class="card">
          <h3>${escapeHtml(item.name)}</h3>
          ${item.evidence ? `<p class="evidence">“${escapeHtml(item.evidence)}”</p>` : ''}
          <p>${escapeHtml(item.feedback)}</p>
          ${
            item.citations.length
              ? `<p class="sources">Sources: ${item.citations
                  .map((citation) => `${escapeHtml(citation.source)} (${escapeHtml(citation.chunk_id)})`)
                  .join(' · ')}</p>`
              : ''
          }
        </article>`,
    )
    .join('');

  const strengths = (report?.strengths ?? [])
    .map((item) => `<li>${escapeHtml(strengthText(item))}</li>`)
    .join('');

  const transcript = session.turns
    .map(
      (turn, index) => `
        <section class="qa">
          <header>
            <span class="q-index">Q${index + 1}</span>
            <span class="q-type">${escapeHtml(turn.question.question_type)}</span>
            <span class="q-comps">${turn.question.targeted_competencies.map(escapeHtml).join(' · ')}</span>
          </header>
          <p class="question">${escapeHtml(turn.question.interviewer_text)}</p>
          ${
            turn.answer
              ? `<p class="answer">${escapeHtml(turn.answer.transcript)}</p>
                 <p class="meta">${turn.answer.elapsed_seconds}s · ${
                   turn.answer.corrected ? 'edited transcript' : 'as spoken'
                 }</p>`
              : '<p class="answer muted">Not answered.</p>'
          }
        </section>`,
    )
    .join('');

  const citations = (report?.citations ?? [])
    .map(
      (citation) => `
        <li>
          <strong>${escapeHtml(citation.source)}</strong>
          <span class="muted">${escapeHtml(citation.chunk_id)}</span>
          <p>${escapeHtml(citation.text)}</p>
        </li>`,
    )
    .join('');

  const limitations = (report?.limitations ?? []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');

  const metrics = report?.speech_metrics;
  const metricBlock = metrics
    ? `<div class="metrics">
         ${metric('Answers', metrics.answer_count)}
         ${metric('Words', metrics.word_count)}
         ${metric('Minutes', (metrics.duration_seconds / 60).toFixed(1))}
         ${metric('Words / min', metrics.words_per_minute ?? '—')}
         ${metric('Fillers', metrics.filler_count)}
         ${metric('Pauses', metrics.pause_count ?? '—')}
       </div>`
    : '';

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>VoxPrep HK — ${escapeHtml(session.role_title)}</title>
<style>
  @page { size: A4; margin: 16mm 14mm 18mm; }
  * { box-sizing: border-box; }
  body {
    margin: 0; color: ${PALETTE.ink}; background: #fff;
    font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 10.5pt; line-height: 1.5;
  }
  h1, h2, h3 { margin: 0; font-weight: 650; letter-spacing: -0.01em; }
  h1 { font-size: 24pt; }
  h2 { font-size: 13pt; margin-bottom: 8px; }
  h3 { font-size: 11pt; }
  p { margin: 0 0 8px; }
  .cover {
    background: ${PALETTE.ink}; color: ${PALETTE.cream};
    padding: 22mm 16mm; margin: -16mm -14mm 10mm; 
  }
  .cover .eyebrow { color: ${PALETTE.gold}; font-size: 9pt; letter-spacing: .18em; text-transform: uppercase; }
  .cover h1 { color: #fff; margin: 6px 0 10px; }
  .cover .sub { color: #cfe0d8; font-size: 11pt; }
  .cover .facts { margin-top: 16px; display: flex; gap: 22px; font-size: 9.5pt; color: #cfe0d8; }
  section { margin-bottom: 14px; break-inside: avoid; }
  .section-title { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  .section-title::after { content: ''; flex: 1; height: 1px; background: ${PALETTE.line}; }
  table { width: 100%; border-collapse: collapse; font-size: 9.5pt; }
  th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid ${PALETTE.line}; vertical-align: top; }
  tr.missing td, tr.missing th { color: ${PALETTE.muted}; }
  td.evidence { font-style: italic; color: ${PALETTE.teal}; }
  .cards { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .card { border: 1px solid ${PALETTE.line}; border-radius: 10px; padding: 10px 12px; break-inside: avoid; }
  .card h3 { color: ${PALETTE.teal}; margin-bottom: 4px; }
  .evidence { color: ${PALETTE.teal}; font-style: italic; }
  .sources, .muted { color: ${PALETTE.muted}; font-size: 8.5pt; }
  .metrics { display: flex; gap: 6px; flex-wrap: wrap; }
  .metric { border: 1px solid ${PALETTE.line}; border-radius: 10px; padding: 8px 12px; min-width: 92px; }
  .metric-value { display: block; font-size: 15pt; font-weight: 650; }
  .metric-label { display: block; font-size: 8pt; color: ${PALETTE.muted}; text-transform: uppercase; letter-spacing: .08em; }
  .qa { border-left: 3px solid ${PALETTE.gold}; padding: 4px 0 4px 12px; margin-bottom: 12px; break-inside: avoid; }
  .qa header { display: flex; gap: 10px; font-size: 8.5pt; color: ${PALETTE.muted}; text-transform: uppercase; letter-spacing: .08em; }
  .qa .question { font-weight: 600; margin: 4px 0 6px; }
  .qa .answer { background: ${PALETTE.cream}; border-radius: 8px; padding: 8px 10px; }
  .qa .meta { color: ${PALETTE.muted}; font-size: 8.5pt; margin-top: 4px; }
  ul { margin: 0 0 8px 18px; padding: 0; }
  li { margin-bottom: 4px; }
  .callout { background: ${PALETTE.cream}; border-radius: 10px; padding: 10px 12px; }
  .callout strong { color: ${PALETTE.teal}; }
  .foot { margin-top: 16px; border-top: 1px solid ${PALETTE.line}; padding-top: 8px; color: ${PALETTE.muted}; font-size: 8pt; }
  .page-break { break-before: page; }
</style>
</head>
<body>
  <header class="cover">
    <div class="eyebrow">VoxPrep HK · interview practice report</div>
    <h1>${escapeHtml(session.role_title)}</h1>
    <div class="sub">${escapeHtml(language)} · ${escapeHtml(session.difficulty)} · ${answers.length} of ${
    session.question_count
  } answered</div>
    <div class="facts">
      <span>Generated ${escapeHtml(date)}</span>
      <span>Model: ${escapeHtml(provider)}</span>
      <span>Session ${escapeHtml(session.id.slice(0, 8))}</span>
    </div>
  </header>

  ${
    report
      ? `<section>
    <div class="section-title"><h2>Summary</h2></div>
    ${paragraphs(report.summary)}
  </section>

  <section>
    <div class="section-title"><h2>STAR evidence</h2></div>
    <table>
      <thead><tr><th>Element</th><th>Present</th><th>Evidence from your answer</th><th>Coaching</th></tr></thead>
      <tbody>${star}</tbody>
    </table>
  </section>

  <section>
    <div class="section-title"><h2>Competencies</h2></div>
    <div class="cards">${competencies || '<p class="muted">No competency feedback was returned.</p>'}</div>
  </section>

  <section>
    <div class="section-title"><h2>What worked</h2></div>
    ${strengths ? `<ul>${strengths}</ul>` : '<p class="muted">No strengths were quoted.</p>'}
    <div class="callout">
      <p><strong>Priority improvement.</strong> ${escapeHtml(report.prioritized_improvement)}</p>
      <p><strong>Retry exercise.</strong> ${escapeHtml(report.retry_exercise)}</p>
    </div>
  </section>

  <section>
    <div class="section-title"><h2>Speech metrics</h2></div>
    ${metricBlock}
  </section>`
      : `<section><div class="section-title"><h2>Debrief</h2></div><p class="muted">This session has no debrief yet, so only the transcript is printed.</p></section>`
  }

  <section class="page-break">
    <div class="section-title"><h2>Full transcript</h2></div>
    ${transcript || '<p class="muted">No questions were answered.</p>'}
  </section>

  ${
    citations
      ? `<section>
    <div class="section-title"><h2>Sources cited</h2></div>
    <ul class="sources-list">${citations}</ul>
  </section>`
      : ''
  }

  ${
    limitations
      ? `<section>
    <div class="section-title"><h2>Limitations</h2></div>
    <ul>${limitations}</ul>
  </section>`
      : ''
  }

  <p class="foot">Generated locally by VoxPrep HK. This report is practice feedback, not an assessment of the person, and it is not a hiring recommendation.</p>
</body>
</html>`;
}

/** Open the printable report; the reader saves it as PDF from the browser dialog. */
export async function printSessionReport(id: string): Promise<void> {
  const session = await api.session(id);
  const report = session.state === 'completed' ? await api.report(id) : null;
  if (report && report.session_id !== session.id) {
    throw new Error('The debrief does not match this session. Reload before exporting.');
  }
  const html = buildReportHtml(session, report);
  const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
  const win = window.open(url, '_blank');
  if (!win) {
    URL.revokeObjectURL(url);
    throw new Error('Allow pop-ups for this site to open the printable report.');
  }
  // Let the new document lay out before the print dialog opens.
  win.addEventListener('load', () => {
    window.setTimeout(() => {
      win.focus();
      win.print();
    }, 250);
  });
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
