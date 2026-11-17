import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFile } from 'node:fs/promises';

for (const language of ['English', '廣東話']) {
  test(`complete ${language} practice and export`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto('/');
    await page.getByRole('button', { name: 'Try a sample role' }).click();
    await page.getByRole('radio', { name: new RegExp('^' + language) }).check();
    await page.getByLabel('Number of questions').selectOption('3');
    await page.getByRole('button', { name: 'Start my interview' }).click();
    await expect(page).toHaveURL(/#\/interview\//);
    await expect(page.getByLabel('Your answer')).toBeVisible();
    const accessibility = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();
    for (let i = 0; i < 3; i++) {
      const answer =
        language === 'English'
          ? 'During a university team project, I was responsible for a slow Python API. I measured SQL query times, added an index, wrote tests and explained the change to teammates. As a result latency fell by 30 percent and all integration tests passed.'
          : '喺大學小組專題入面，我負責改善一個緩慢嘅 Python API。我量度 SQL 查詢時間，加入索引，寫測試，同隊友解釋修改。結果回應時間減少咗三成，所有整合測試都通過。';
      await page.getByLabel('Your answer').fill(answer);
      await page
        .getByRole('button', { name: 'Send answer', exact: true })
        .click();
      if (i < 2) await expect(page.getByLabel('Your answer')).toHaveValue('');
    }
    await expect(
      page.getByRole('heading', { name: 'Make your next answer stronger.' }),
    ).toBeVisible();
    await expect(page).toHaveURL(/#\/report\//);
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export report' }).click();
    expect((await downloadPromise).suggestedFilename()).toMatch(
      /^voxprep-debrief-.*\.json$/,
    );
    expect(
      accessibility.violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => ({
          target: n.target,
          failure: n.failureSummary,
        })),
      })),
    ).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test('practice opens first with a read-only configuration summary and validates setup', async ({
  page,
}) => {
  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: 'Practice interview', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'Overview', exact: true }),
  ).toHaveCount(0);
  const summary = page.getByRole('complementary', {
    name: 'Configuration status',
  });
  const start = page.getByRole('button', { name: 'Start my interview' });
  await expect(start).toBeDisabled();
  await expect(summary.locator('input, select, textarea')).toHaveCount(0);
  await expect(page.getByRole('checkbox')).toHaveCount(0);
  await expect(
    page.getByText(
      /Your story stays yours|A space to grow|LOCAL-FIRST PRACTICE|Made for your next opportunity|Enable Azure/,
    ),
  ).toHaveCount(0);
  await page.getByLabel('Job description', { exact: true }).fill('Too short');
  await expect(start).toBeDisabled();
  await page.getByRole('button', { name: 'Try a sample role' }).click();
  await page.getByRole('radio', { name: /^廣東話/ }).check();
  await page.getByLabel('Difficulty', { exact: true }).selectOption('stretch');
  await page.getByLabel('Number of questions').selectOption('8');
  await expect(start).toBeEnabled();
  await expect(summary).toContainText('廣東話');
  await expect(summary).toContainText('Stretch');
  await expect(summary).toContainText('8');
  await page.getByLabel('Job description', { exact: true }).fill('');
  await expect(start).toBeDisabled();
});

test('practice and history have no critical accessibility violations on mobile', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: 'Practice interview', exact: true }),
  ).toBeVisible();
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze())
      .violations,
  ).toEqual([]);
  await page.getByRole('link', { name: 'History', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'History', exact: true }),
  ).toBeVisible();
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze())
      .violations,
  ).toEqual([]);
});

test('resume, pause, skip, retry and microphone denial preserve typed practice', async ({
  page,
  request,
}) => {
  const profileResponse = await request.post('/api/job-profiles', {
    data: {
      title: 'Browser recovery case',
      text: 'Graduate developer. Build Python APIs, write automated tests, use SQL databases, and communicate technical tradeoffs with teammates.',
    },
  });
  const profile = await profileResponse.json();
  const sessionResponse = await request.post('/api/sessions', {
    data: {
      job_profile_id: profile.id,
      language: 'en-HK',
      difficulty: 'standard',
      question_count: 3,
      store_transcript: true,
    },
  });
  const session = await sessionResponse.json();
  await page.goto(`/#/interview/${session.id}`);
  await page.getByRole('button', { name: 'Hide interviewer' }).click();
  await page
    .getByRole('button', { name: 'Record answer', exact: true })
    .click();
  await expect(
    page.getByText('Microphone access is unavailable.', { exact: false }),
  ).toBeVisible();
  await page
    .getByLabel('Your answer')
    .fill('I built a Python API during a university project and wrote tests.');
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await expect(page.getByLabel('Your answer')).toBeDisabled();
  await page.getByRole('button', { name: 'Resume practice' }).click();
  await expect(page.getByLabel('Your answer')).toHaveValue(
    'I built a Python API during a university project and wrote tests.',
  );
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

test('compare completed evidence and export the full saved transcript', async ({
  page,
  request,
}) => {
  const sessions: { id: string; role_title: string }[] = [];
  const transcripts = [
    'I helped on a Python project.',
    'During our project I owned API testing. I added regression tests and reduced failures by 30 percent.',
  ];
  try {
    for (let i = 0; i < 2; i++) {
      const profile = await (
        await request.post('/api/job-profiles', {
          data: {
            title: `Comparison fixture ${i + 1}`,
            text: 'Graduate software engineer. Implement Python APIs, write tests, use SQL and explain technical decisions to teammates.',
          },
        })
      ).json();
      const session = await (
        await request.post('/api/sessions', {
          data: {
            job_profile_id: profile.id,
            language: 'en-HK',
            difficulty: 'standard',
            question_count: 3,
            store_transcript: true,
          },
        })
      ).json();
      sessions.push(session);
      expect(
        (
          await request.post(`/api/sessions/${session.id}/answer`, {
            data: {
              turn_id: session.turns[0].id,
              transcript: transcripts[i],
              language: 'en-HK',
              elapsed_seconds: 30,
              corrected: false,
            },
          })
        ).ok(),
      ).toBeTruthy();
      expect(
        (
          await request.post(`/api/sessions/${session.id}/control`, {
            data: { action: 'end' },
          })
        ).ok(),
      ).toBeTruthy();
    }
    await page.goto('/#/history');
    for (const session of sessions) {
      await page
        .getByRole('checkbox', {
          name: new RegExp(`^Compare ${session.role_title} from`),
        })
        .check();
    }
    await expect(
      page.getByRole('heading', { name: 'Compare your practice' }),
    ).toBeVisible();
    await expect(
      page.getByRole('article', {
        name: `First session: ${sessions[0].role_title}`,
      }),
    ).toContainText(transcripts[0]);
    await expect(
      page.getByRole('article', {
        name: `Second session: ${sessions[1].role_title}`,
      }),
    ).toContainText('30 percent');
    const downloading = page.waitForEvent('download');
    await page
      .getByRole('button', {
        name: `Export full session for ${sessions[0].role_title}`,
        exact: true,
      })
      .click();
    const download = await downloading;
    const content = JSON.parse(
      await readFile((await download.path())!, 'utf8'),
    );
    expect(content.format).toBe('voxprep.session');
    expect(content.session.id).toBe(sessions[0].id);
    expect(content.session.turns[0].answer.transcript).toBe(transcripts[0]);
    expect(
      content.session.turns[0].question.interviewer_text.length,
    ).toBeGreaterThan(0);
    expect(content.report.session_id).toBe(sessions[0].id);
    expect(
      (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze())
        .violations,
    ).toEqual([]);
    await page.getByRole('button', { name: 'Clear comparison' }).click();
    await expect(
      page.getByRole('heading', { name: 'Compare your practice' }),
    ).toHaveCount(0);
  } finally {
    for (const session of sessions)
      await request.delete(`/api/sessions/${session.id}`);
  }
});

test('Jamie is chosen before starting and real preparation stages remain visible during slow requests', async ({
  page,
  request,
}) => {
  let releaseProfile!: () => void;
  let releaseSession!: () => void;
  const profileGate = new Promise<void>((resolve) => {
    releaseProfile = resolve;
  });
  const sessionGate = new Promise<void>((resolve) => {
    releaseSession = resolve;
  });
  let profileRequests = 0;
  let sessionRequests = 0;
  let submitted: { interviewer?: string } | null = null;
  let sessionId: string | undefined;
  await page.route('**/api/job-profiles', async (route) => {
    if (route.request().method() === 'POST') {
      profileRequests++;
      await profileGate;
    }
    await route.continue();
  });
  await page.route('**/api/sessions', async (route) => {
    if (route.request().method() === 'POST') {
      sessionRequests++;
      submitted = route.request().postDataJSON();
      await sessionGate;
    }
    await route.continue();
  });
  try {
    await page.goto('/');
    await page.evaluate(() =>
      localStorage.setItem('voxprep.interviewer', 'sam'),
    );
    await page.reload();
    const appearance = page.getByRole('group', {
      name: 'Interviewer appearance',
    });
    await expect(appearance.getByRole('radio')).toHaveCount(1);
    await expect(
      appearance.getByRole('radio', { name: 'Jamie', exact: true }),
    ).toBeChecked();
    await expect(
      page.getByRole('complementary', { name: 'Configuration status' }),
    ).toContainText('Jamie');
    await page.getByRole('button', { name: 'Try a sample role' }).click();
    await page.getByLabel('Number of questions').selectOption('3');
    await page.getByRole('button', { name: 'Start my interview' }).click();
    const progress = page.getByRole('progressbar', {
      name: 'Interview preparation',
    });
    await expect(progress).toBeVisible();
    await expect(progress).toHaveAttribute(
      'aria-valuetext',
      'Reading and indexing the job description',
    );
    await expect(progress).not.toHaveAttribute('aria-valuenow');
    await expect(
      page.getByRole('button', { name: 'Preparing your interview…' }),
    ).toBeDisabled();
    await expect(
      page.getByLabel('Job description', { exact: true }),
    ).toBeDisabled();
    await expect(
      appearance.getByRole('radio', { name: 'Jamie' }),
    ).toBeDisabled();
    await expect(page.getByText(/Elapsed 0:0[1-9]/)).toBeVisible({
      timeout: 4000,
    });
    await page.locator('form.setup-grid').evaluate((form) => {
      form.dispatchEvent(
        new Event('submit', { bubbles: true, cancelable: true }),
      );
      form.dispatchEvent(
        new Event('submit', { bubbles: true, cancelable: true }),
      );
    });
    expect(profileRequests).toBe(1);
    expect(sessionRequests).toBe(0);
    releaseProfile();
    await expect(progress).toHaveAttribute(
      'aria-valuetext',
      'Preparing the first question',
    );
    await expect.poll(() => sessionRequests).toBe(1);
    await expect(progress).not.toHaveAttribute('aria-valuenow');
    await page.screenshot({
      path: '../artifacts/verification/interview-preparation.png',
      fullPage: true,
    });
    await page
      .locator('form.setup-grid')
      .evaluate((form) =>
        form.dispatchEvent(
          new Event('submit', { bubbles: true, cancelable: true }),
        ),
      );
    releaseSession();
    await expect(page).toHaveURL(/#\/interview\//);
    sessionId = page.url().split('/interview/')[1];
    await expect(page.getByLabel('Your answer', { exact: true })).toBeVisible();
    expect(profileRequests).toBe(1);
    expect(sessionRequests).toBe(1);
    expect(submitted).toMatchObject({ interviewer: 'jamie' });
    await expect(
      page.getByRole('group', { name: 'Interviewer appearance' }),
    ).toHaveCount(0);
    const saved = await (
      await request.get(`/api/sessions/${sessionId}`)
    ).json();
    expect(saved.interviewer).toBe('jamie');
    const question = await page.locator('.question-card h2').innerText();
    await page.evaluate(() =>
      localStorage.setItem('voxprep.interviewer', 'alex'),
    );
    await page.reload();
    await expect(page).toHaveURL(new RegExp(`#/interview/${sessionId}$`));
    await expect(page.locator('.question-card h2')).toHaveText(question);
    await expect(
      page.getByRole('group', { name: 'Interviewer appearance' }),
    ).toHaveCount(0);
    expect(
      (await (await request.get(`/api/sessions/${sessionId}`)).json())
        .interviewer,
    ).toBe('jamie');
  } finally {
    releaseProfile();
    releaseSession();
    if (sessionId) await request.delete(`/api/sessions/${sessionId}`);
  }
});

test('3D speaking state follows local playback and stops on pause', async ({
  page,
  request,
}) => {
  await expect
    .poll(
      async () => {
        const asset = await request.get('/interviewers/jamie.mesh.json');
        if (!asset.ok()) return false;
        return asset
          .json()
          .then(
            (mesh) =>
              mesh.landmarkCount === 468 && Array.isArray(mesh.positions),
          )
          .catch(() => false);
      },
      { timeout: 10000 },
    )
    .toBe(true);
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.addInitScript(() => {
    let active: SpeechSynthesisUtterance | null = null;
    const controls = {
      spoken: 0,
      canceled: 0,
      start() {
        if (active)
          active.onstart?.call(
            active,
            new Event('start') as SpeechSynthesisEvent,
          );
      },
      boundary() {
        if (active)
          active.onboundary?.call(
            active,
            Object.assign(new Event('boundary'), {
              charIndex: 6,
              charLength: 4,
              name: 'word',
              elapsedTime: 0.2,
            }) as SpeechSynthesisEvent,
          );
      },
    };
    Object.defineProperty(window, '__speechTest', { value: controls });
    Object.defineProperty(window, 'SpeechSynthesisUtterance', {
      configurable: true,
      value: class extends EventTarget {
        constructor(text: string) {
          super();
          Object.defineProperty(this, 'text', { value: text });
        }
      },
    });
    Object.defineProperty(window, 'speechSynthesis', {
      configurable: true,
      value: {
        getVoices: () => [
          {
            name: 'Test local voice',
            lang: 'en-HK',
            localService: true,
            default: true,
            voiceURI: 'test-local',
          },
        ],
        addEventListener() {},
        removeEventListener() {},
        speak(utterance: SpeechSynthesisUtterance) {
          active = utterance;
          controls.spoken++;
        },
        cancel() {
          controls.canceled++;
          active = null;
        },
      },
    });
  });
  const profile = await (
    await request.post('/api/job-profiles', {
      data: {
        title: 'Speech animation case',
        text: 'Graduate developer. Build Python APIs, write automated tests, use SQL databases, and communicate technical tradeoffs with teammates.',
      },
    })
  ).json();
  const session = await (
    await request.post('/api/sessions', {
      data: {
        job_profile_id: profile.id,
        language: 'en-HK',
        difficulty: 'standard',
        question_count: 3,
        interviewer: 'jamie',
      },
    })
  ).json();
  try {
    await page.goto(`/#/interview/${session.id}`);
    await expect(
      page.getByRole('checkbox', { name: 'Read questions automatically' }),
    ).toBeChecked();
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            (window as unknown as { __speechTest: { spoken: number } })
              .__speechTest.spoken,
        ),
      )
      .toBe(1);
    await expect(
      page.getByText('Your interviewer is speaking', { exact: true }),
    ).toHaveCount(0);
    await page.evaluate(() => {
      const speech = (
        window as unknown as {
          __speechTest: { start(): void; boundary(): void };
        }
      ).__speechTest;
      speech.start();
      speech.boundary();
    });
    await expect(
      page.getByText('Your interviewer is speaking', { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Stop audio' }),
    ).toBeVisible();
    const scene = page.getByRole('img', {
      name: 'Jamie, 3D interviewer speaking',
      exact: true,
    });
    await expect(scene.locator('canvas')).toBeVisible({ timeout: 10000 });
    await expect
      .poll(() =>
        scene
          .locator('canvas')
          .evaluate(
            (canvas: HTMLCanvasElement) =>
              canvas.width > 0 && canvas.height > 0,
          ),
      )
      .toBe(true);
    await page.screenshot({
      path: '../artifacts/verification/interview-3d-speaking.png',
      fullPage: true,
    });
    await page.getByRole('button', { name: 'Stop audio' }).click();
    await expect(
      page.getByRole('img', { name: 'Jamie, 3D interviewer', exact: true }),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'Stop audio' })).toHaveCount(
      0,
    );
    await page.getByRole('button', { name: 'Read question' }).click();
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            (window as unknown as { __speechTest: { spoken: number } })
              .__speechTest.spoken,
        ),
      )
      .toBe(2);
    await page.evaluate(() =>
      (
        window as unknown as { __speechTest: { start(): void } }
      ).__speechTest.start(),
    );
    await expect(
      page.getByRole('button', { name: 'Stop audio' }),
    ).toBeVisible();
    const canceled = await page.evaluate(
      () =>
        (window as unknown as { __speechTest: { canceled: number } })
          .__speechTest.canceled,
    );
    await page.getByRole('button', { name: 'Pause', exact: true }).click();
    await expect(
      page.getByRole('button', { name: 'Resume practice' }),
    ).toBeVisible();
    await expect(
      page.getByRole('img', { name: 'Jamie, 3D interviewer', exact: true }),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'Stop audio' })).toHaveCount(
      0,
    );
    expect(
      await page.evaluate(
        () =>
          (window as unknown as { __speechTest: { canceled: number } })
            .__speechTest.canceled,
      ),
    ).toBeGreaterThan(canceled);
    await page.getByRole('button', { name: 'Hide interviewer' }).click();
    await expect(
      page.getByText('Interviewer hidden', { exact: true }),
    ).toBeVisible();
    await expect(page.locator('.interviewer-3d-canvas canvas')).toHaveCount(0);
    await page.getByRole('button', { name: 'Show interviewer' }).click();
    await expect(page.locator('.interviewer-3d-canvas canvas')).toBeVisible({
      timeout: 10000,
    });
  } finally {
    await request.delete(`/api/sessions/${session.id}`);
  }
});
