import { test, expect } from '@playwright/test';

test('Run waits for project selection and prevents switching while a run starts', async ({ page, request }) => {
  const id = 'selection-' + Date.now().toString(36);
  const spec = {
    spec_version: '0.3', id, input_schema: { type: 'object' }, output_schema: {},
    models: {}, tools: {}, resources: {},
    graph: { entry: 'review', nodes: { review: { type: 'human', output_schema: { type: 'object' }, inputs: {} } },
      edges: [], output: { answer: { ref: 'nodes.review.output' } } },
  };
  expect((await request.post('/api/projects', { data: { spec } })).status()).toBe(201);
  await page.goto('/');
  await page.locator('.project[title="hello"]').click();
  await expect(page.locator('h1')).toHaveText('hello');
  let releaseProject!: () => void;
  let releaseRun!: () => void;
  const projectGate = new Promise<void>(resolve => { releaseProject = resolve; });
  const runGate = new Promise<void>(resolve => { releaseRun = resolve; });
  await page.route(`**/api/projects/${id}`, async route => {
    await projectGate;
    await route.continue();
  });
  const starts: string[] = [];
  await page.route('**/api/projects/*/runs', async route => {
    starts.push(new URL(route.request().url()).pathname);
    await runGate;
    await route.continue();
  });
  const run = page.getByRole('button', { name: '▷ Run', exact: true });
  try {
    await page.locator(`.project[title="${id}"]`).click();
    await expect(run).toBeDisabled();
    expect(starts).toEqual([]);
    releaseProject();
    await expect(page.locator('h1')).toHaveText(id);
    await run.click();
    await expect.poll(() => starts).toEqual([`/api/projects/${id}/runs`]);
    await expect(run).toBeDisabled();
    await expect(page.locator('.project[title="hello"]')).toBeDisabled();
    releaseRun();
    await expect(page.getByRole('button', { name: 'Submit and continue', exact: true })).toBeVisible();
    await expect(page.locator('h1')).toHaveText(id);
  } finally {
    releaseProject();
    releaseRun();
  }
});

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

test('view navigation waits for project creation to finish before editing a spec', async ({ page, request }) => {
  await page.goto('/');
  await page.locator('.project[title="hello"]').click();
  await expect(page.locator('h1')).toHaveText('hello');
  await expect(page.locator('.editor')).toHaveAttribute('aria-busy', 'false');
  let releaseRefresh!: () => void;
  const refreshGate = new Promise<void>(resolve => { releaseRefresh = resolve; });
  await page.route('**/api/projects', async route => {
    if (route.request().method() === 'GET') await refreshGate;
    await route.continue();
  });
  try {
    const created = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/projects');
    await page.getByRole('button', { name: '＋ New project' }).click();
    const id = (await (await created).json()).id;
    await expect(page.locator('h1')).toHaveText(id);
    await expect(page.locator('.editor')).toHaveAttribute('aria-busy', 'true');
    for (const view of ['Canvas', 'Spec', 'Python', 'Resources', 'History', 'Memory', 'Improve', 'Versions']) {
      await expect(page.getByRole('button', { name: view, exact: true })).toBeDisabled();
    }
    releaseRefresh();
    await page.getByRole('button', { name: 'Spec', exact: true }).click();
    const editor = page.getByLabel('AgentSpec JSON');
    const draft = JSON.parse(await editor.inputValue());
    draft.graph.nodes.assistant.instructions = 'Keep the first edit after project creation.';
    await editor.fill(JSON.stringify(draft, null, 2));
    await page.getByRole('button', { name: 'Canvas', exact: true }).click();
    await expect(page.locator('.react-flow__node')).toContainText(draft.graph.nodes.assistant.instructions);
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('Saved');
    const saved = await (await request.get('/api/projects/' + id)).json();
    expect(saved.spec.graph.nodes.assistant.instructions).toBe(draft.graph.nodes.assistant.instructions);
  } finally {
    releaseRefresh();
  }
});
