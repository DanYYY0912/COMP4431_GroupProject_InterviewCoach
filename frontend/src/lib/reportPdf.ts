import { api } from './api';
import type { Report, Session } from './types';

/**
 * Printable session report.
 *
 * The PDF is produced by the browser's own "Save as PDF" from a purpose-built print document:
 * the styling stays the app's palette, the text stays selectable, and no PDF library is added.
 *
 * Layout rule: page 1 must answer "how did this go and what do I fix first". Sources, the
 * transcript and the limitations are appendices, and long source passages are trimmed to one
 * line each so the report never becomes a wall of government text.
 *
 * The only number in the report scores answer *structure* (STAR coverage, quoted evidence,
 * pacing, fillers). The app may not score the person, so no ability or employability grade
 * appears anywhere.
 */

const C = {
  ink: '#203d34',
  teal: '#256456',
  cream: '#f6f4ed',
  gold: '#d8b779',
  muted: '#5c6b64',
  line: '#dfe3dc',
  good: '#2f7a5f',
  warn: '#c9861f',
  bad: '#a8432c',
  white: '#ffffff',
};

const LABELS = {
  en: {
    eyebrow: 'VoxPrep HK · interview practice report',
    model: 'Model',
    session: 'Session',
    star: 'STAR coverage',
    starJump: '(transcript · Appendix A)',
    noStar: 'No STAR analysis was returned.',
    worked: 'What worked',
    nothingQuoted: 'Nothing was quoted.',
    fixFirst: 'Fix this first',
    priority: 'Priority improvement',
    retry: 'Retry',
    delivery: 'Delivery',
    answers: 'Answers',
    answersNote: 'completed',
    words: 'Words',
    wordsNote: 'total spoken',
    fillers: 'Fillers',
    pauses: 'Pauses',
    notMeasured: 'not measured',
    competencies: 'Competencies',
    strongest: 'Your strongest evidence',
    shareKicker: 'Strongest evidence',
    shareHint: 'Screenshot this frame to share it — the 16:9 box is sized for a clean crop.',
    appendixA: 'Appendix A · transcript',
    appendixB: 'Appendix B · sources cited',
    appendixC: 'Appendix C · limitations',
    back: '(back to summary)',
    noAnswers: 'No questions were answered.',
    foot: 'Generated locally by VoxPrep HK. Practice feedback only — not an assessment of the person and not a hiring recommendation.',
    structure: 'STRUCTURE',
    disclaimer:
      'Answer structure only — STAR coverage, quoted evidence, pacing and fillers. Not an assessment of you, your ability or your employability.',
    perMin: '/ min',
    answeredOf: (a: number, n: number) => `${a} of ${n} answered`,
    langName: 'English (en-HK)',
    diff: { foundation: 'foundation', standard: 'standard', stretch: 'stretch' } as Record<string, string>,
    wpmUnit: 'wpm',
    gaugeIn: 'inside the 120–150 wpm range most interviewers find easy to follow',
    gaugeSlow: 'slower than the 120–150 wpm range most interviewers find easy to follow',
    gaugeFast: 'faster than the 120–150 wpm range most interviewers find easy to follow',
    gaugeNone: 'not measured in this session',
    starNames: { Situation: 'Situation', Task: 'Task', Action: 'Action', Result: 'Result' } as Record<string, string>,
    covered: 'covered',
    missing: 'missing',
    partStar: 'STAR coverage',
    partEvidence: 'Quoted evidence',
    partPacing: 'Pacing',
    partFillers: 'Filler control',
    of4: (n: number) => `${n} of 4 elements evidenced`,
    ofComps: (q: number, n: number) => `${q} of ${n} competencies quoted`,
    fillersIn: (f: number, m: string) => `${f} fillers / ${m} min`,
  },
  'zh-HK': {
    eyebrow: 'VoxPrep HK · 面試練習報告',
    model: '模型',
    session: '場次',
    star: 'STAR 覆蓋',
    starJump: '（逐字稿 · 附錄 A）',
    noStar: '未收到 STAR 分析。',
    worked: '做得好的地方',
    nothingQuoted: '未引用到具體句子。',
    fixFirst: '先改呢一點',
    priority: '優先改善',
    retry: '再試一次',
    delivery: '表達節奏',
    answers: '回答',
    answersNote: '已完成',
    words: '字詞',
    wordsNote: '總字數',
    fillers: '填充詞',
    pauses: '停頓',
    notMeasured: '未量度',
    competencies: '能力項',
    strongest: '你最有力的證據',
    shareKicker: '最強證據',
    shareHint: '截圖呢個框就可以分享 — 16:9 尺寸，方便裁切。',
    appendixA: '附錄 A · 逐字稿',
    appendixB: '附錄 B · 引用來源',
    appendixC: '附錄 C · 限制',
    back: '（返回摘要）',
    noAnswers: '未有任何回答。',
    foot: '由 VoxPrep HK 本機生成。只屬練習回饋，並非對個人嘅評分，亦非招聘建議。',
    structure: '結構',
    disclaimer:
      '只計答案結構：STAR 覆蓋、引用證據、語速、填充詞。並非評估你個人、能力或就業能力。',
    perMin: '／分鐘',
    answeredOf: (a: number, n: number) => `已回答 ${a} / ${n}`,
    langName: '廣東話 (zh-HK)',
    diff: { foundation: '基礎', standard: '標準', stretch: '挑戰' } as Record<string, string>,
    wpmUnit: '字／分鐘',
    gaugeIn: '喺 120–150 字／分鐘範圍內，面試官最容易跟得上',
    gaugeSlow: '慢過 120–150 字／分鐘，面試官會覺得節奏偏慢',
    gaugeFast: '快過 120–150 字／分鐘，面試官可能跟唔上',
    gaugeNone: '今次未量度',
    starNames: { Situation: '背景', Task: '任務', Action: '行動', Result: '結果' } as Record<string, string>,
    covered: '已覆蓋',
    missing: '缺少',
    partStar: 'STAR 覆蓋',
    partEvidence: '引用證據',
    partPacing: '語速',
    partFillers: '填充詞控制',
    of4: (n: number) => `4 項中 ${n} 項有證據`,
    ofComps: (q: number, n: number) => `${n} 項能力中 ${q} 項有引用`,
    fillersIn: (f: number, m: string) => `${f} 個填充詞／${m} 分鐘`,
  },
};
type Labels = (typeof LABELS)['en'];

function esc(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function strengthText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value && typeof value === 'object' && 'text' in value) return String((value as { text: string }).text);
  return '';
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Words per minute only means something against a band, so draw the band, not a bare number. */
function wpmGauge(wpm: number | null, L: Labels): string {
  const low = 90;
  const high = 180;
  const width = 320;
  const bandStart = ((120 - low) / (high - low)) * width;
  const bandEnd = ((150 - low) / (high - low)) * width;
  const x = wpm === null ? 0 : clamp(((wpm - low) / (high - low)) * width, 0, width);
  const tone =
    wpm === null ? C.muted : wpm >= 120 && wpm <= 150 ? C.good : wpm >= 100 && wpm <= 170 ? C.warn : C.bad;
  const verdict =
    wpm === null ? L.gaugeNone : wpm < 120 ? L.gaugeSlow : wpm > 150 ? L.gaugeFast : L.gaugeIn;
  return `<figure class="gauge">
    <svg viewBox="0 0 ${width} 54" width="100%" height="54" role="img" aria-label="Speaking rate ${
      wpm === null ? 'unmeasured' : `${Math.round(wpm)} words per minute`
    }">
      <rect x="0" y="16" width="${width}" height="12" rx="6" fill="${C.line}"></rect>
      <rect x="${bandStart}" y="16" width="${bandEnd - bandStart}" height="12" fill="${C.good}" opacity="0.3"></rect>
      <rect x="0" y="16" width="${clamp(x, 6, width)}" height="12" rx="6" fill="${tone}"></rect>
      <circle cx="${clamp(x, 8, width - 8)}" cy="22" r="9" fill="${C.white}" stroke="${tone}" stroke-width="4"></circle>
      <text x="${bandStart}" y="10" font-size="9" fill="${C.good}">120</text>
      <text x="${bandEnd}" y="10" font-size="9" fill="${C.good}">150</text>
      <text x="0" y="50" font-size="9" fill="${C.muted}">${low}</text>
      <text x="${width}" y="50" font-size="9" fill="${C.muted}" text-anchor="end">${high}+</text>
    </svg>
    <figcaption><strong style="color:${tone}">${wpm === null ? '—' : Math.round(wpm)} wpm</strong> · ${esc(
      verdict,
    )}</figcaption>
  </figure>`;
}

function structureScore(report: Report, L: Labels): { score: number; grade: string; parts: [string, number, string][] } {
  const starPresent = report.star.filter((item) => item.present).length;
  const starPoints = Math.round((starPresent / 4) * 40);
  const quoted = report.competencies.filter((item) => item.evidence).length;
  const evidencePoints = report.competencies.length
    ? Math.round((quoted / report.competencies.length) * 20)
    : 0;
  const wpm = report.speech_metrics.words_per_minute;
  const pacePoints = wpm === null ? 10 : wpm >= 120 && wpm <= 150 ? 20 : wpm >= 100 && wpm <= 170 ? 13 : 6;
  const minutes = Math.max(report.speech_metrics.duration_seconds / 60, 0.1);
  const fillersPerMinute = report.speech_metrics.filler_count / minutes;
  const fillerPoints = fillersPerMinute <= 2 ? 20 : fillersPerMinute <= 5 ? 12 : 5;
  const score = starPoints + evidencePoints + pacePoints + fillerPoints;
  return {
    score,
    grade: score >= 85 ? 'A' : score >= 70 ? 'B' : score >= 55 ? 'C' : 'D',
    parts: [
      [L.partStar, starPoints, L.of4(starPresent)],
      [L.partEvidence, evidencePoints, L.ofComps(quoted, report.competencies.length)],
      [L.partPacing, pacePoints, wpm === null ? L.notMeasured : `${Math.round(wpm)} ${L.wpmUnit}`],
      [L.partFillers, fillerPoints, L.fillersIn(report.speech_metrics.filler_count, minutes.toFixed(1))],
    ],
  };
}

/** Vector ring: stays sharp when a reader zooms in on a phone. */
function scoreRing(score: number, grade: string, L: Labels): string {
  const radius = 31;
  const circumference = 2 * Math.PI * radius;
  const filled = (score / 100) * circumference;
  const tone = score >= 85 ? C.good : score >= 70 ? C.teal : score >= 55 ? C.warn : C.bad;
  return `<div class="score-badge">
    <svg viewBox="0 0 88 88" width="88" height="88" role="img" aria-label="Answer structure ${score} out of 100">
      <circle cx="44" cy="44" r="${radius}" fill="none" stroke="${C.line}" stroke-width="8"></circle>
      <circle cx="44" cy="44" r="${radius}" fill="none" stroke="${tone}" stroke-width="8"
        stroke-dasharray="${filled.toFixed(1)} ${(circumference - filled).toFixed(1)}"
        stroke-linecap="round" transform="rotate(-90 44 44)"></circle>
      <text x="44" y="45" text-anchor="middle" font-size="23" font-weight="700" fill="${C.ink}">${score}</text>
      <text x="44" y="59" text-anchor="middle" font-size="8.5" fill="${C.muted}">/100</text>
    </svg>
    <span class="score-grade">${L.structure} ${grade}</span>
  </div>`;
}

function starCard(item: Report['star'][number], L: Labels): string {
  const tone = item.present ? C.good : C.warn;
  return `<article class="star-card" style="border-top-color:${tone}">
    <header>
      <span class="star-mark" style="background:${tone}">${item.present ? '✓' : '!'}</span>
      <h4>${esc(L.starNames[item.element] ?? item.element)}</h4>
      <span class="star-state" style="color:${tone}">${item.present ? L.covered : L.missing}</span>
    </header>
    ${
      item.evidence
        ? `<blockquote>“${esc(item.evidence)}”</blockquote>`
        : '<p class="muted">No sentence in your answer covered this element.</p>'
    }
    <p class="coaching">${esc(item.coaching)}</p>
  </article>`;
}

function tile(label: string, value: string, note: string, tone: string = C.ink): string {
  return `<div class="tile"><span class="tile-value" style="color:${tone}">${esc(value)}</span>
    <span class="tile-label">${esc(label)}</span><span class="tile-note">${esc(note)}</span></div>`;
}

export function buildReportHtml(
  session: Session,
  report: Report | null,
  exportedAt = new Date(),
  appUrl = 'http://localhost:5173',
): string {
  const base = appUrl.replace(/\/$/, '');
  const L = LABELS[session.language === 'zh-HK' ? 'zh-HK' : 'en'];
  const language = session.language === 'zh-HK' ? 'Cantonese (zh-HK)' : 'English (en-HK)';
  const date = exportedAt.toLocaleDateString(session.language === 'zh-HK' ? 'zh-HK' : 'en-HK', { dateStyle: 'medium' });
  const answered = session.turns.filter((turn) => turn.answer).length;
  const metrics = report?.speech_metrics ?? null;
  const score = report ? structureScore(report, L) : null;

  const stars = (report?.star ?? []).map((item) => starCard(item, L)).join('');
  const strengths = (report?.strengths ?? []).map((item) => `<li>${esc(strengthText(item))}</li>`).join('');

  // The strongest evidence containing a number is the most shareable line in the report.
  const highlight =
    (report?.star ?? [])
      .map((item) => item.evidence)
      .filter((evidence) => /\d/.test(evidence))
      .sort((a, b) => b.length - a.length)[0] ?? '';

  const competencyRows = (report?.competencies ?? [])
    .map(
      (item) => `<tr><th>${esc(item.name)}</th><td>${esc(item.feedback)}</td>
        <td class="cite">${item.citations.length ? esc(item.citations[0].source.slice(0, 28)) : '—'}</td></tr>`,
    )
    .join('');

  const transcript = session.turns
    .map(
      (turn, index) => `<section class="qa">
        <header><span class="q">Q${index + 1}</span><span>${esc(turn.question.question_type)}</span>
          <span>${turn.question.targeted_competencies.map(esc).join(' · ')}</span></header>
        <p class="question">${esc(turn.question.interviewer_text)}</p>
        ${
          turn.answer
            ? `<p class="answer">${esc(
                turn.answer.transcript.length > 900
                  ? `${turn.answer.transcript.slice(0, 900)}…`
                  : turn.answer.transcript,
              )}</p>
               <p class="meta">${turn.answer.elapsed_seconds.toFixed(1)}s · ${turn.answer.corrected ? 'edited' : 'as spoken'}</p>`
            : '<p class="answer muted">Not answered.</p>'
        }
      </section>`,
    )
    .join('');

  const sources = (report?.citations ?? [])
    .map((citation) => {
      const passage = citation.text.replace(/\s+/g, ' ');
      return `<li><strong>${esc(citation.source)}</strong> <span class="muted">${esc(citation.chunk_id)}</span>
        <p class="snippet">${esc(passage.slice(0, 160))}${passage.length > 160 ? '…' : ''}</p></li>`;
    })
    .join('');

  const limitations = (report?.limitations ?? []).map((item) => `<li>${esc(item)}</li>`).join('');

  const scoreBlock = score
    ? `<section class="score-band">
        ${scoreRing(score.score, score.grade, L)}
        <div class="score-parts">
          ${score.parts
            .map(
              ([label, points, note]) =>
                `<div class="part"><span class="part-points">${points}</span><span class="part-label">${esc(
                  label,
                )}</span><span class="part-note">${esc(note)}</span></div>`,
            )
            .join('')}
        </div>
      </section>
      <p class="disclaimer">${L.disclaimer}</p>`
    : '';

  const fillersPerMinute =
    metrics && metrics.duration_seconds > 0 ? metrics.filler_count / Math.max(metrics.duration_seconds / 60, 0.1) : null;

  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<title>VoxPrep HK — ${esc(session.role_title)}</title>
<style>
  @page { size: A4; margin: 14mm 13mm 16mm; }
  * { box-sizing: border-box; }
  body { margin:0; color:${C.ink}; font-family:'Helvetica Neue',Arial,sans-serif; font-size:10pt; line-height:1.45;
    -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  h1,h2,h3,h4 { margin:0; font-weight:650; letter-spacing:-.01em; }
  p { margin:0 0 6px; }
  .muted { color:${C.muted}; }
  /* Inset card, not full bleed: negative margins get cropped by the print page box. */
  .cover { background:#ffffff; color:${C.ink}; padding:11mm 12mm 9mm; margin:0 0 7mm; border-radius:14px; border:1px solid ${C.line}; border-left:6px solid ${C.teal}; }
  .eyebrow { color:${C.teal}; font-size:7.5pt; letter-spacing:.2em; text-transform:uppercase; font-weight:600; }
  .cover h1 { color:${C.ink}; font-size:21pt; margin:5px 0 4px; }
  .cover .sub { color:${C.muted}; font-size:9.5pt; }
  .facts { margin-top:8px; display:flex; gap:16px; font-size:7.5pt; color:${C.muted}; border-top:1px solid ${C.line}; padding-top:6px; }
  .score-band { display:flex; gap:12px; border:1px solid ${C.line}; border-radius:14px; padding:11px; margin-bottom:5px; break-inside:avoid; }
  .score-badge { display:flex; flex-direction:column; justify-content:center; align-items:center; padding:2px 8px; }
  .score-number { font-size:28pt; font-weight:700; line-height:1; }
  .score-number small { font-size:9.5pt; font-weight:500; color:${C.muted}; }
  .score-badge { gap:5px; }
  .score-grade { font-size:7pt; color:${C.teal}; letter-spacing:.12em; text-transform:uppercase; margin-top:1px; }
  .score-parts { display:grid; grid-template-columns:1fr 1fr; gap:5px 12px; flex:1; }
  .part { display:flex; flex-direction:column; }
  .part-points { font-size:11.5pt; font-weight:700; color:${C.teal}; line-height:1.1; }
  .part-label { font-size:8.5pt; font-weight:600; }
  .part-note { font-size:7pt; color:${C.muted}; }
  .disclaimer { font-size:7pt; color:${C.muted}; margin:0 0 10px; }
  h2.section { font-size:11.5pt; margin:0 0 6px; display:flex; align-items:center; gap:8px; }
  h2.section::after { content:''; flex:1; height:1px; background:${C.line}; }
  section { margin-bottom:13px; break-inside:avoid; }
  .stars { display:grid; grid-template-columns:1fr 1fr; gap:11px; }
  .star-card { border:1px solid ${C.line}; border-top:3px solid ${C.good}; border-radius:12px; padding:12px 14px; break-inside:avoid; }
  .star-card header { display:flex; align-items:center; gap:6px; margin-bottom:4px; }
  .star-mark { width:15px; height:15px; border-radius:50%; color:#fff; font-size:8.5pt; font-weight:700; display:flex; align-items:center; justify-content:center; }
  .star-card h4 { font-size:9.5pt; }
  .star-state { margin-left:auto; font-size:7pt; text-transform:uppercase; letter-spacing:.1em; }
  .star-card blockquote { margin:0 0 7px; padding-left:8px; border-left:2px solid ${C.line}; font-style:italic; color:${C.teal}; font-size:8.5pt; line-height:1.5; }
  .star-card .coaching { font-size:8.5pt; margin:0; line-height:1.5; }
  .two-col { display:grid; grid-template-columns:1fr 1fr; gap:11px; }
  .callout.action { background:#ffffff; border:1px solid ${C.gold}; border-radius:13px; padding:11px 13px; }
  .callout.action h3 { color:${C.teal}; font-size:7.5pt; text-transform:uppercase; letter-spacing:.12em; margin-bottom:3px; }
  .callout.action p { margin:0; font-size:10.5pt; line-height:1.3; }
  .cta { margin-top:7px; display:flex; align-items:center; gap:9px; background:#fff; border:1px solid ${C.teal}; color:${C.ink}; border-radius:999px; padding:8px 14px; font-size:9pt; text-decoration:none; }
  .cta em { margin-left:auto; font-style:normal; color:${C.teal}; font-size:11pt; }
  .jump { font-size:7pt; font-weight:500; color:${C.teal}; text-decoration:none; border-bottom:1px dotted ${C.teal}; }
  .cta strong { color:${C.teal}; text-transform:uppercase; letter-spacing:.1em; font-size:7pt; }
  ul { margin:0 0 5px 15px; padding:0; }
  li { margin-bottom:2px; }
  .tiles { display:grid; grid-template-columns:repeat(4,1fr); gap:6px; }
  .tile { border:1px solid ${C.line}; border-radius:9px; padding:7px 8px; }
  .tile-value { display:block; font-size:14pt; font-weight:700; line-height:1.1; }
  .tile-label { display:block; font-size:7pt; text-transform:uppercase; letter-spacing:.08em; color:${C.muted}; }
  .tile-note { display:block; font-size:6.5pt; color:${C.muted}; opacity:.85; }
  figure.gauge { margin:4px 0 0; }
  figure.gauge figcaption { font-size:8pt; color:${C.muted}; }
  table { width:100%; border-collapse:collapse; font-size:8.5pt; }
  th,td { text-align:left; padding:5px 6px; border-bottom:1px solid ${C.line}; vertical-align:top; }
  th { font-weight:650; white-space:nowrap; }
  td.cite { color:${C.muted}; font-size:7pt; width:26%; }
  .share-card { position:relative; height:102mm; border:1px solid ${C.line}; border-radius:16px; background:#ffffff;
    padding:16mm 15mm; display:flex; flex-direction:column; justify-content:center; break-inside:avoid;
    box-shadow: 0 2mm 6mm rgba(32,61,52,.10); }
  .share-kicker { font-size:8pt; letter-spacing:.18em; text-transform:uppercase; color:${C.teal}; font-weight:600; margin-bottom:6px; }
  .share-card .quote { font-size:15pt; font-style:italic; color:${C.teal}; line-height:1.4; margin:0 0 10px; }
  .share-meta { font-size:8pt; color:${C.muted}; }
  .share-logo { position:absolute; right:15mm; bottom:12mm; font-size:15pt; font-weight:600; letter-spacing:-.01em; color:${C.ink}; }
  .share-logo b { color:${C.gold}; font-weight:700; }
  .share-hint { font-size:7pt; color:${C.muted}; margin-top:5px; }
  .highlight .quote { font-size:11pt; font-style:italic; color:${C.teal}; margin-bottom:3px; }
  .highlight .brand { font-size:7pt; letter-spacing:.16em; text-transform:uppercase; color:${C.muted}; }
  .page-break { break-before:page; }
  .qa { border-left:3px solid ${C.gold}; padding:1px 0 1px 9px; margin-bottom:8px; break-inside:avoid; }
  .qa header { display:flex; gap:8px; font-size:7pt; color:${C.muted}; text-transform:uppercase; letter-spacing:.08em; }
  .qa .q { font-weight:700; color:${C.teal}; }
  .qa .question { font-weight:600; font-size:8.5pt; margin:2px 0 3px; }
  .qa .answer { font-size:8pt; background:#ffffff; border:1px solid ${C.line}; border-radius:6px; padding:5px 7px; }
  .qa .meta { font-size:7pt; color:${C.muted}; margin-top:2px; }
  .sources-list { list-style:none; margin:0; padding:0; }
  .sources-list li { margin-bottom:5px; break-inside:avoid; }
  .snippet { font-size:7pt; color:${C.muted}; margin:1px 0 0; }
  .foot { margin-top:10px; border-top:1px solid ${C.line}; padding-top:5px; font-size:6.5pt; color:${C.muted}; }
</style></head>
<body id="top">
  <header class="cover">
    <div class="eyebrow">${L.eyebrow}</div>
    <h1>${esc(session.role_title)}</h1>
    <div class="sub">${esc(L.langName)} · ${esc(L.diff[session.difficulty] ?? session.difficulty)} · ${esc(
      L.answeredOf(answered, session.question_count),
    )}</div>
    <div class="facts"><span>${esc(date)}</span><span>${L.model}: ${esc(session.provider || 'unknown')}</span>
      <span>${L.session} ${esc(session.id.slice(0, 8))}</span></div>
  </header>

  ${scoreBlock}

  <section>
    <h2 class="section">${L.star} <a class="jump" href="#appendix-a">${L.starJump}</a></h2>
    <div class="stars">${stars || '<p class="muted">' + L.noStar + '</p>'}</div>
  </section>

  <div class="two-col">
    <section>
      <h2 class="section">${L.worked}</h2>
      ${strengths ? `<ul>${strengths}</ul>` : '<p class="muted">' + L.nothingQuoted + '</p>'}
    </section>
    <section>
      <h2 class="section">${L.fixFirst}</h2>
      <div class="callout action">
        <h3>${L.priority}</h3>
        <p>${esc(report?.prioritized_improvement ?? '—')}</p>
      </div>
      ${
        report
          ? `<a class="cta" href="${base}/#/setup?retry=1&from=${encodeURIComponent(
              session.id,
            )}&lang=${encodeURIComponent(
              session.language,
            )}"><strong>${L.retry}</strong><span>${esc(report.retry_exercise)}</span><em>›</em></a>`
          : ''
      }
    </section>
  </div>

  ${
    metrics
      ? `<section>
    <h2 class="section">${L.delivery}</h2>
    ${wpmGauge(metrics.words_per_minute, L)}
    <div class="tiles" style="margin-top:7px">
      ${tile(L.answers, String(metrics.answer_count), L.answersNote)}
      ${tile(L.words, String(metrics.word_count), L.wordsNote)}
      ${tile(
        L.fillers,
        String(metrics.filler_count),
        fillersPerMinute === null ? '—' : `${fillersPerMinute.toFixed(1)} ${L.perMin}`,
        fillersPerMinute !== null && fillersPerMinute <= 2 ? C.good : C.warn,
      )}
      ${tile(
        L.pauses,
        metrics.pause_count === null || metrics.pause_count === undefined ? '—' : String(metrics.pause_count),
        metrics.silence_seconds ? `${metrics.silence_seconds}s silence` : L.notMeasured,
      )}
    </div>
  </section>`
      : ''
  }

  ${
    competencyRows
      ? `<section><h2 class="section">${L.competencies}</h2><table><tbody>${competencyRows}</tbody></table></section>`
      : ''
  }

  ${
    highlight
      ? `<section><h2 class="section">${L.strongest}</h2>
    <div class="share-card">
      <span class="share-kicker">${L.shareKicker}</span>
      <p class="quote">“${esc(highlight.slice(0, 190))}${highlight.length > 190 ? '…' : ''}”</p>
      <span class="share-meta">${esc(session.role_title)} · ${esc(language)}</span>
      <span class="share-logo">VoxPrep<b>HK</b></span>
    </div>
    <p class="share-hint">${L.shareHint}</p></section>`
      : ''
  }

  <div class="page-break appendix">
    <section id="appendix-a">
      <h2 class="section">${L.appendixA} <a class="jump" href="#top">${L.back}</a></h2>
      ${transcript || '<p class="muted">' + L.noAnswers + '</p>'}
    </section>
    ${
      sources
        ? `<section id="appendix-b"><h2 class="section">${L.appendixB}</h2><ul class="sources-list">${sources}</ul></section>`
        : ''
    }
    ${limitations ? `<section><h2 class="section">${L.appendixC}</h2><ul>${limitations}</ul></section>` : ''}
  </div>

  <p class="foot">${L.foot}</p>
</body></html>`;
}

/** Open the printable report; the reader saves it as PDF from the browser dialog. */
export async function printSessionReport(id: string): Promise<void> {
  const session = await api.session(id);
  const report = session.state === 'completed' ? await api.report(id) : null;
  if (report && report.session_id !== session.id) {
    throw new Error('The debrief does not match this session. Reload before exporting.');
  }
  const html = buildReportHtml(session, report, new Date(), window.location.origin);
  const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
  const win = window.open(url, '_blank');
  if (!win) {
    URL.revokeObjectURL(url);
    throw new Error('Allow pop-ups for this site to open the printable report.');
  }
  win.addEventListener('load', () => {
    window.setTimeout(() => {
      win.focus();
      win.print();
    }, 250);
  });
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
