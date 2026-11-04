import { test, expect, type Page } from '@playwright/test';
import path from 'node:path';

test.beforeEach(async ({ page }) => { await page.addInitScript(() => localStorage.setItem('evosprig.language', 'zh')); });
async function createProject(page: Page) {
  await page.goto('/');
  const creation = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/projects');
  await page.getByRole('button', { name: '＋ 新建项目' }).click();
  const id = (await (await creation).json()).id;
  await expect(page.locator('h1')).toHaveText(id);
  await page.locator('.react-flow__node').click();
  return id;
}

test('project changes can be kept, saved before switching, or explicitly discarded', async ({ page, request }) => {
  const id = await createProject(page);
  await page.getByLabel('指令', { exact: true }).fill('Keep this instruction.');
  await page.locator('.project[title="hello"]').click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: '继续编辑' })).toBeFocused();
  const evidence = process.env.EVOSPRIG_EVIDENCE_DIR;
  if (evidence) await page.screenshot({ path: path.join(evidence, 'studio-draft-protection.png') });
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(page.getByLabel('指令', { exact: true })).toHaveValue('Keep this instruction.');
  await page.locator('.project[title="hello"]').click();
  await dialog.getByRole('button', { name: '保存并继续' }).click();
  await expect(page.locator('h1')).toHaveText('hello');
  const saved = await (await request.get(`/api/projects/${id}`)).json();
  expect(saved.spec.graph.nodes.assistant.instructions).toBe('Keep this instruction.');
  await page.locator(`.project[title="${id}"]`).click();
  await expect(page.locator('h1')).toHaveText(id);
  await page.locator('.react-flow__node').click();
  await page.getByLabel('指令', { exact: true }).fill('Discard this edit.');
  await page.getByRole('button', { name: '重新加载', exact: true }).first().click();
  await dialog.getByRole('button', { name: '放弃修改' }).click();
  await expect(dialog).not.toBeVisible();
  await page.locator('.react-flow__node').click();
  await expect(page.getByLabel('指令', { exact: true })).toHaveValue('Keep this instruction.');
});

test('invalid node drafts survive failed saves and canceled page reloads', async ({ page, request }) => {
  const id = await createProject(page);
  await page.locator('.advanced-node > summary').click();
  const editor = page.getByLabel('完整节点（JSON）');
  const draft = JSON.parse(await editor.inputValue());
  await editor.fill('{');
  const reloadDialog = page.waitForEvent('dialog');
  const reloading = page.reload({ timeout: 2000 }).catch(() => null);
  const warning = await reloadDialog;
  expect(warning.type()).toBe('beforeunload');
  await warning.dismiss();
  await reloading;
  await expect(editor).toHaveValue('{');
  await page.locator('.project[title="hello"]').click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: '保存并继续' }).click();
  await expect(dialog.getByRole('alert')).not.toBeEmpty();
  await expect(page.locator('h1')).toHaveText(id);
  await dialog.getByRole('button', { name: '继续编辑' }).click();
  await expect(editor).toHaveValue('{');
  draft.instructions = 'Saved directly from the node JSON draft.';
  await editor.fill(JSON.stringify(draft));
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('已保存');
  const saved = await (await request.get(`/api/projects/${id}`)).json();
  expect(saved.spec.graph.nodes.assistant.instructions).toBe(draft.instructions);
  await page.reload();
  await expect(page.locator('h1')).toBeVisible();
});
