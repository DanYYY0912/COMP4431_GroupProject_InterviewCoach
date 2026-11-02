import { defineConfig } from '@playwright/test';
import path from 'node:path';
const root = path.resolve(import.meta.dirname, '..');
export default defineConfig({
  testDir: './tests', fullyParallel: false, workers: 1, timeout: 45_000,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:8009', trace: 'retain-on-failure', screenshot: 'only-on-failure', video: 'retain-on-failure', reducedMotion: 'reduce' },
  webServer: {
    command: `"${root}/.venv/bin/python" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8009`,
    cwd: root, url: 'http://127.0.0.1:8009/api/health', reuseExistingServer: !process.env.CI,
    env: { MODEL_PROVIDER: 'demo', DATABASE_URL: 'sqlite:///./artifacts/e2e.db', ALLOWED_ORIGINS: 'http://127.0.0.1:8009', AZURE_SPEECH_KEY: '', EMBEDDING_BASE_URL: '', RERANKER_BASE_URL: '' },
  },
});
