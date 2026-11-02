import { test, expect } from '@playwright/test';

test('map can be created, saved, reloaded and executed from Studio', async ({ page, request }) => {
  await page.goto('/');
  const created = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/projects');
  await page.getByRole('button', { name: 'New project' }).click();
  const { id } = await (await created).json();
  await expect(page.locator('h1')).toHaveText(id);
  await page.getByLabel('New node type').selectOption('map');
  await page.getByRole('button', { name: 'Add node', exact: true }).click();
  await page.getByRole('button', { name: 'Spec', exact: true }).click();
  const editor = page.getByLabel('AgentSpec JSON');
  const spec = JSON.parse(await editor.inputValue());
  expect(spec.spec_version).toBe('0.3');
  const mapId = Object.keys(spec.graph.nodes).find(key => spec.graph.nodes[key].type === 'map')!;
  // Keep only the new map and expose its body outputs.
  spec.graph = { entry: mapId, nodes: { [mapId]: spec.graph.nodes[mapId] }, edges: [], output: { results: { ref: `nodes.${mapId}.output.items` } } };
  spec.models = {};
  spec.output_schema = { type: 'object', properties: { results: { type: 'array' } }, required: ['results'] };
  await editor.fill(JSON.stringify(spec, null, 2));
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Saved');
  const before = await (await request.get(`/api/projects/${id}`)).json();
  await page.reload();
  await page.locator(`.project[title="${id}"]`).click();
  await expect(page.locator('h1')).toHaveText(id);
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Saved');
  const after = await (await request.get(`/api/projects/${id}`)).json();
  expect(after.spec_hash).toBe(before.spec_hash);
  await page.getByRole('button', { name: '▷ Run', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('succeeded');
  await expect(page.locator('.results')).toContainText('first');
  await expect(page.locator('.results')).toContainText('second');
});
