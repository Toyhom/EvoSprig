import { test, expect } from '@playwright/test';

test('a late startup response preserves the newly created project and its task suite', async ({ page, request }) => {
  let releaseStartup!: () => void;
  let startupCaptured!: () => void;
  const release = new Promise<void>(resolve => { releaseStartup = resolve; });
  const captured = new Promise<void>(resolve => { startupCaptured = resolve; });
  let first = true;
  await page.route('**/api/projects', async route => {
    if (route.request().method() !== 'GET' || !first) return route.continue();
    first = false;
    const response = await route.fetch();
    startupCaptured();
    await release;
    await route.fulfill({ response });
  });
  await page.goto('/');
  await captured;
  const created = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/projects');
  await page.getByRole('button', { name: 'New project' }).click();
  const id = (await (await created).json()).id;
  await expect(page.locator('h1')).toHaveText(id);
  await expect(page.getByRole('button', { name: 'New project' })).toBeEnabled();
  const startupReturned = page.waitForResponse(r => r.request().method() === 'GET' && new URL(r.url()).pathname === '/api/projects');
  releaseStartup();
  await startupReturned;
  // Let fetch callbacks and React's next paint complete before reading the active project.
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(page.locator('h1')).toHaveText(id);
  await expect(page.locator(`.project[title="${id}"]`)).toBeVisible();
  await page.getByRole('button', { name: 'Improve', exact: true }).click();
  await page.getByLabel('Task inputs JSON').fill(JSON.stringify(['pricing', 'roadmap', 'support', 'launch'].map(question => ({ question }))));
  const saved = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname === `/api/projects/${id}/suites/from-inputs`);
  await page.getByRole('button', { name: 'Create task suite', exact: true }).click();
  const response = await saved;
  expect(response.status()).toBe(201);
  const suiteId = (await response.json()).suite_id;
  await expect(page.getByLabel('Evaluation suite', { exact: true })).toHaveValue(suiteId);
  const suites = await (await request.get(`/api/projects/${id}/suites`)).json();
  expect(suites.find((suite: { suite_id: string }) => suite.suite_id === suiteId).suite.metric.kind).toBe('llm_judge');
});
