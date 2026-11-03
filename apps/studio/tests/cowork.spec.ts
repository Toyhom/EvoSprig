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
  await page.goto('/cowork.html?project=' + id);
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
  await expect(page.locator('#headline')).toHaveText('从需求到交付。');
});
