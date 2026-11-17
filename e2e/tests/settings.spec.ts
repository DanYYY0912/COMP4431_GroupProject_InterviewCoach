import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { createServer, type Server } from 'node:http';
import type { AddressInfo } from 'node:net';

const sections = ['Agent', 'ASR', 'Embedding', 'Reranker'];
let server: Server;
let base: string;
const received: { path: string; authorization: string }[] = [];

test.beforeAll(async () => {
  server = createServer((request, response) => {
    received.push({ path: request.url || '', authorization: request.headers.authorization || '' });
    response.setHeader('Content-Type', 'application/json');
    response.end(JSON.stringify({ data: sections.map(name => ({ id: `${name.toLowerCase()}-fixture` })) }));
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

test.afterAll(async () => {
  await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
});

test('four inference sections save, discover models and retain redacted keys after reload', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  const original = await (await request.get('/api/inference-settings')).json();
  try {
    await page.goto('/#/settings');
    for (const section of sections) {
      const slug = section.toLowerCase();
      await page.getByLabel(`${section} base URL`, { exact: true }).fill(`${base}/${slug}/v1`);
      await page.getByLabel(`${section} API key`, { exact: true }).fill(`fixture-${slug}-secret`);
      const discovery = page.waitForResponse(response => response.url().endsWith(`/api/inference-settings/${slug}/models`));
      await page.getByRole('group', { name: section, exact: true }).getByRole('button', { name: 'Load models' }).click();
      expect((await discovery).ok()).toBeTruthy();
      await page.getByLabel(`${section} model`, { exact: true }).fill(`${slug}-fixture`);
    }
    const saving = page.waitForResponse(response => response.url().endsWith('/api/inference-settings') && response.request().method() === 'PUT');
    await page.getByRole('button', { name: 'Save settings', exact: true }).click();
    expect((await saving).ok()).toBeTruthy();
    await page.reload();
    const saved = await (await request.get('/api/inference-settings')).json();
    for (const section of sections) {
      const slug = section.toLowerCase();
      await expect(page.getByLabel(`${section} base URL`, { exact: true })).toHaveValue(`${base}/${slug}/v1`);
      await expect(page.getByLabel(`${section} model`, { exact: true })).toHaveValue(`${slug}-fixture`);
      await expect(page.getByLabel(`${section} API key`, { exact: true })).toHaveValue('');
      expect(saved[slug]).toEqual({ base_url: `${base}/${slug}/v1`, model: `${slug}-fixture`, api_key_set: true });
      expect(received).toContainEqual({ path: `/${slug}/v1/models`, authorization: `Bearer fixture-${slug}-secret` });
    }
    expect(JSON.stringify(saved)).not.toContain('secret');
    expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations).toEqual([]);
    await page.setViewportSize({ width: 390, height: 844 });
    expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations).toEqual([]);
    await page.screenshot({ path: '../artifacts/verification/settings-mobile.png', fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.screenshot({ path: '../artifacts/verification/settings-desktop.png', fullPage: true });
    expect(errors).toEqual([]);
  } finally {
    await request.put('/api/inference-settings', { data: Object.fromEntries(sections.map(name => {
      const slug = name.toLowerCase();
      return [slug, { base_url: original[slug].base_url, model: original[slug].model, api_key: '' }];
    })) });
  }
});
