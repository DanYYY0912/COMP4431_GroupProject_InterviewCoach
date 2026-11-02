import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFile } from 'node:fs/promises';

for (const language of ['English', '廣東話']) {
  test(`complete ${language} practice and export`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('/');
    await page.getByRole('button', { name: 'Start a practice interview' }).click();
    await page.getByRole('button', { name: 'Try a sample role' }).click();
    await page.getByRole('radio', { name: new RegExp('^' + language) }).check();
    await page.getByLabel('Number of questions').selectOption('3');
    await page.getByLabel('Save this session and transcript on this computer', { exact: false }).check();
    await page.getByRole('button', { name: 'Start my interview' }).click();
    await expect(page).toHaveURL(/#\/interview\//);
    await expect(page.getByLabel('Your answer')).toBeVisible();
    const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    for (let i = 0; i < 3; i++) {
      const answer = language === 'English'
        ? 'During a university team project, I was responsible for a slow Python API. I measured SQL query times, added an index, wrote tests and explained the change to teammates. As a result latency fell by 30 percent and all integration tests passed.'
        : '喺大學小組專題入面，我負責改善一個緩慢嘅 Python API。我量度 SQL 查詢時間，加入索引，寫測試，同隊友解釋修改。結果回應時間減少咗三成，所有整合測試都通過。';
      await page.getByLabel('Your answer').fill(answer);
      await page.getByRole('button', { name: 'Send answer', exact: true }).click();
      if (i < 2) await expect(page.getByLabel('Your answer')).toHaveValue('');
    }
    await expect(page.getByRole('heading', { name: 'Make your next answer stronger.' })).toBeVisible();
    await expect(page).toHaveURL(/#\/report\//);
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export report' }).click();
    expect((await downloadPromise).suggestedFilename()).toMatch(/^voxprep-debrief-.*\.json$/);
    expect(accessibility.violations.map(v => ({id: v.id, nodes: v.nodes.map(n => ({target:n.target, failure:n.failureSummary}))}))).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test('dashboard and setup have no critical accessibility violations on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Start a practice interview' })).toBeVisible();
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations.map(v => ({id: v.id, nodes: v.nodes.map(n => ({target:n.target, failure:n.failureSummary}))}))).toEqual([]);
  await page.getByRole('button', { name: 'Start a practice interview' }).click();
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations.map(v => ({id: v.id, nodes: v.nodes.map(n => ({target:n.target, failure:n.failureSummary}))}))).toEqual([]);
});

test('resume, pause, skip, retry and microphone denial preserve typed practice', async ({ page, request }) => {
  const profileResponse = await request.post('/api/job-profiles', { data: { title: 'Browser recovery case', text: 'Graduate developer. Build Python APIs, write automated tests, use SQL databases, and communicate technical tradeoffs with teammates.' } });
  const profile = await profileResponse.json();
  const sessionResponse = await request.post('/api/sessions', { data: { job_profile_id: profile.id, language: 'en-HK', difficulty: 'standard', question_count: 3, store_transcript: true } });
  const session = await sessionResponse.json();
  await page.goto(`/#/interview/${session.id}`);
  await page.getByRole('button', { name: 'Disable animated avatar' }).click();
  await page.getByRole('button', { name: 'Record answer', exact: true }).click();
  await expect(page.getByText('Microphone access is unavailable.', { exact: false })).toBeVisible();
  await page.getByLabel('Your answer').fill('I built a Python API during a university project and wrote tests.');
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await expect(page.getByLabel('Your answer')).toBeDisabled();
  await page.getByRole('button', { name: 'Resume practice' }).click();
  await expect(page.getByLabel('Your answer')).toHaveValue('I built a Python API during a university project and wrote tests.');
  await page.getByRole('button', { name: 'Send answer', exact: true }).click();
  await expect(page.getByLabel('Your answer')).toHaveValue('');
  await page.reload();
  await expect(page.getByText('Question 2', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Skip question' }).click();
  await expect(page.getByText('Question 3', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Finish & review' }).click();
  await expect(page).toHaveURL(/#\/report\//);
  await page.getByRole('button', { name: 'Practise this again' }).click();
  await expect(page).toHaveURL(/#\/interview\//);
  await expect(page.getByLabel('Your answer')).toBeEnabled();
  const deleted = await request.delete(`/api/sessions/${session.id}`);
  expect(deleted.status()).toBe(204);
  expect((await request.get(`/api/sessions/${session.id}`)).status()).toBe(404);
});

test('compare completed evidence and export the full saved transcript', async ({ page, request }) => {
  const sessions: { id: string; role_title: string }[] = [];
  const transcripts = [
    'I helped on a Python project.',
    'During our project I owned API testing. I added regression tests and reduced failures by 30 percent.',
  ];
  try {
    for (let i = 0; i < 2; i++) {
      const profile = await (await request.post('/api/job-profiles', { data: {
        title: `Comparison fixture ${i + 1}`,
        text: 'Graduate software engineer. Implement Python APIs, write tests, use SQL and explain technical decisions to teammates.',
      } })).json();
      const session = await (await request.post('/api/sessions', { data: {
        job_profile_id: profile.id, language: 'en-HK', difficulty: 'standard',
        question_count: 3, store_transcript: true,
      } })).json();
      sessions.push(session);
      expect((await request.post(`/api/sessions/${session.id}/answer`, { data: {
        turn_id: session.turns[0].id, transcript: transcripts[i],
        language: 'en-HK', elapsed_seconds: 30, corrected: false,
      } })).ok()).toBeTruthy();
      expect((await request.post(`/api/sessions/${session.id}/control`, { data: { action: 'end' } })).ok()).toBeTruthy();
    }
    await page.goto('/');
    for (const session of sessions) {
      await page.getByRole('checkbox', { name: new RegExp(`^Compare ${session.role_title} from`) }).check();
    }
    await expect(page.getByRole('heading', { name: 'Compare your practice' })).toBeVisible();
    await expect(page.getByRole('article', { name: `First session: ${sessions[0].role_title}` })).toContainText(transcripts[0]);
    await expect(page.getByRole('article', { name: `Second session: ${sessions[1].role_title}` })).toContainText('30 percent');
    const downloading = page.waitForEvent('download');
    await page.getByRole('button', { name: `Export full session for ${sessions[0].role_title}`, exact: true }).click();
    const download = await downloading;
    const content = JSON.parse(await readFile((await download.path())!, 'utf8'));
    expect(content.format).toBe('voxprep.session');
    expect(content.session.id).toBe(sessions[0].id);
    expect(content.session.turns[0].answer.transcript).toBe(transcripts[0]);
    expect(content.session.turns[0].question.interviewer_text.length).toBeGreaterThan(0);
    expect(content.report.session_id).toBe(sessions[0].id);
    expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations).toEqual([]);
    await page.getByRole('button', { name: 'Clear comparison' }).click();
    await expect(page.getByRole('heading', { name: 'Compare your practice' })).toHaveCount(0);
  } finally {
    for (const session of sessions) await request.delete(`/api/sessions/${session.id}`);
  }
});
