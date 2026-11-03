import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test('cowork documents preserve edits on conflict and render untrusted text safely', async ({ page, request }) => {
  const id = 'cowork-ui-' + Date.now().toString(36);
  const spec = { spec_version: '0.3', id, input_schema: {}, output_schema: {}, models: {}, tools: {}, resources: {}, graph: { entry: 'draft', nodes: { draft: { type: 'transform', inputs: {}, output_schema: {} } }, edges: [], output: {} } };
  expect((await request.post('/api/projects', { data: { spec } })).status()).toBe(201);
  const root = '/api/projects/' + id + '/workspace';
  expect((await request.put(root + '/document', { data: { name: 'plan.md', content: '# Launch\n<script>window.injected=true</script>', expected_revision: 0, operation_id: 'create' } })).status()).toBe(200);
  for (const [url, file, type] of [['/cowork.html', 'index.html', 'text/html'], ['/app.js', 'app.js', 'text/javascript'], ['/style.css', 'style.css', 'text/css']]) {
    await page.route('**' + url + '*', async route => route.fulfill({ body: await readFile('../cowork/' + file), contentType: type }));
  }
  await page.route('**/fonts/**', async route => {
    const file = new URL(route.request().url()).pathname.split('/').pop();
    await route.fulfill({ body: await readFile('../cowork/fonts/' + file), contentType: file?.endsWith('.css') ? 'text/css' : 'font/woff2' });
  });
  await page.goto('/cowork.html?project=' + id);
  await expect(page).toHaveTitle('CoworkOS (EvoSprig)');
  await expect(page.locator('.brand')).toHaveText('CoworkOS (EvoSprig)');
  await page.locator('#documents button').click();
  await expect(page.locator('#document-content')).toContainText('<script>window.injected=true</script>');
  expect(await page.evaluate(() => (window as any).injected)).toBeUndefined();
  await page.locator('#edit').click();
  await page.locator('#document-editor').fill('# My unsaved edit');
  await request.put(root + '/document', { data: { name: 'plan.md', content: '# Saved by the agent', expected_revision: 1, operation_id: 'agent-change' } });
  await page.locator('#save').click();
  await expect(page.locator('#error')).toContainText('revision 2');
  await expect(page.locator('#document-editor')).toHaveValue('# My unsaved edit');
  page.on('dialog', d => d.accept());
  await page.locator('#documents button').click();
  await expect(page.locator('#document-content')).toContainText('Saved by the agent');
  await page.locator('#edit').click();
  await page.locator('#document-editor').fill('# Merged edit');
  await page.locator('#save').click();
  await expect(page.locator('#revision')).toContainText('Revision 3');
  await expect(page.locator('#history button')).toHaveCount(3);
  await page.locator('#language').selectOption('zh');
  await expect(page.locator('#edit')).toHaveText('编辑');
  await page.reload();
  await expect(page.locator('#language')).toHaveValue('zh');
  await expect(page.locator('#headline')).toHaveText('这次一起做什么？');
});


test('cowork switches conversations, clears new tasks and opens the mobile task panel', async ({ page, request }) => {
  const id = 'cowork-navigation-' + Date.now().toString(36);
  const spec = { spec_version: '0.3', id, input_schema: {}, output_schema: {}, models: {}, tools: {}, resources: {}, graph: { entry: 'draft', nodes: { draft: { type: 'transform', inputs: {}, output_schema: {} } }, edges: [], output: {} } };
  await request.post('/api/projects', { data: { spec } });
  const runs = [];
  for (const text of ['Plan the spring launch', 'Prepare a customer workshop']) {
    const started = await request.post('/api/projects/' + id + '/runs', { data: { input: { request: text }, revision: 1, mock: true } });
    runs.push((await started.json()).run_id);
  }
  for (const id of runs) await expect.poll(async () => (await (await request.get('/api/runs/' + id)).json()).status).toBe('succeeded');
  await request.put('/api/projects/' + id + '/workspace/document', { data: { name: 'launch.md', content: '# Launch plan', expected_revision: 0, operation_id: 'create' } });
  for (const [url, file, type] of [['/cowork.html', 'index.html', 'text/html'], ['/app.js', 'app.js', 'text/javascript'], ['/style.css', 'style.css', 'text/css']]) {
    await page.route('**' + url + '*', async route => route.fulfill({ body: await readFile('../cowork/' + file), contentType: type }));
  }
  await page.route('**/fonts/**', async route => {
    const file = new URL(route.request().url()).pathname.split('/').pop();
    await route.fulfill({ body: await readFile('../cowork/fonts/' + file), contentType: file?.endsWith('.css') ? 'text/css' : 'font/woff2' });
  });
  await page.goto('/cowork.html?project=' + id);
  await expect(page.locator('#conversations button')).toHaveCount(2);
  await page.locator('#conversations button').filter({ hasText: 'spring launch' }).click();
  await expect(page.locator('#submitted-request')).toHaveText('Plan the spring launch');
  await page.locator('#new-task').click();
  await expect(page.locator('#welcome')).toBeVisible();
  await expect(page.locator('#conversation')).toBeHidden();
  await expect(page.locator('#cancel')).toBeHidden();
  await page.locator('#request').fill('An unsent task');
  await page.waitForTimeout(2800);
  await expect(page.locator('#request')).toHaveValue('An unsent task');
  await expect(page.locator('#welcome')).toBeVisible();
  await page.locator('#conversations button').filter({ hasText: 'customer workshop' }).click();
  await expect(page.locator('#submitted-request')).toHaveText('Prepare a customer workshop');
  await page.locator('#theme').click();
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('#panel-toggle').click();
  await expect(page.locator('#task-panel')).toBeVisible();
  await page.locator('#documents button').click();
  await expect(page.locator('#document-content')).toContainText('Launch plan');
  await expect(page.locator('#task-panel')).toBeHidden();
  await page.locator('#close-document').click();
  await expect(page.locator('#team-view')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1000 });
  const reviewSpec = { ...spec, graph: { entry: 'review', nodes: { review: { type: 'human', inputs: { draft: { value: 'A draft for review' } }, output_schema: {} } }, edges: [], output: {} } };
  await request.put('/api/projects/' + id, { data: { spec: reviewSpec, revision: 1 } });
  const reviewRun = await request.post('/api/projects/' + id + '/runs', { data: { input: { request: 'Review a proposal' }, revision: 2, mock: true } });
  const reviewId = (await reviewRun.json()).run_id;
  await expect.poll(async () => (await (await request.get('/api/runs/' + reviewId)).json()).status).toBe('waiting_input');
  await page.locator('#refresh').click();
  await page.locator('#conversations button').filter({ hasText: 'Review a proposal' }).click();
  await expect(page.locator('#review-text')).toHaveValue('A draft for review');
  await page.locator('#review-text').fill('My edited approval draft');
  await page.locator('#conversations button').filter({ hasText: 'Review a proposal' }).click();
  await page.waitForTimeout(2800);
  await expect(page.locator('#review-text')).toHaveValue('My edited approval draft');
  page.once('dialog', dialog => dialog.dismiss());
  await page.locator('#new-task').click();
  await expect(page.locator('#review-text')).toHaveValue('My edited approval draft');
  page.once('dialog', dialog => dialog.accept());
  await page.locator('#new-task').click();
  await expect(page.locator('#welcome')).toBeVisible();

});
