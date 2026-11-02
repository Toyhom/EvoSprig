import { defineConfig } from '@playwright/test';

// Keep local readiness checks local when the developer shell has an HTTP proxy.
process.env.NO_PROXY = [process.env.NO_PROXY, '127.0.0.1', 'localhost', '::1'].filter(Boolean).join(',');
process.env.no_proxy = process.env.NO_PROXY;

export default defineConfig({
  testDir: './tests',
  timeout: 90_000,
  workers: 1,
  expect: { timeout: 15_000 },
  webServer: {
    command: `${process.env.EVOSPRIG_PYTHON || 'python'} -m evosprig.cli serve --workspace "${process.env.EVOSPRIG_TEST_WORKSPACE || '../../.evosprig/e2e'}" --project ../../examples/hello/agent.yaml --studio-dir dist --port 18765`,
    url: 'http://127.0.0.1:18765/api/health',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
  use: { baseURL: process.env.EVOSPRIG_STUDIO_URL || 'http://127.0.0.1:18765', viewport: { width: 1440, height: 1000 } },
  reporter: 'list',
});
