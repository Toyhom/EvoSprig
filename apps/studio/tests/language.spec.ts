import { test, expect } from '@playwright/test';

test('English is the default and Chinese persists across reloads', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('button', { name: 'New project' })).toBeVisible();
  await page.getByRole('button', { name: '中文 / EN' }).click();
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN');
  await expect(page.getByRole('button', { name: '新建项目' })).toBeVisible();
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN');
  await page.getByRole('button', { name: '中文 / EN' }).click();
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await page.locator('.project[title="hello"]').click();
  await page.getByRole('button', { name: 'Improve', exact: true }).click();
  await expect(page.getByLabel('Evolution method').locator('option')).toHaveCount(23);
});

test('context block edits and temporal relations are usable in Studio', async ({ page }) => {
  await page.goto('/');
  const created = page.waitForResponse(r => r.request().method()==='POST' && new URL(r.url()).pathname==='/api/projects');
  await page.getByRole('button', {name:'New project'}).click();
  const project = await (await created).json();
  await expect(page.locator('h1')).toHaveText(project.id);
  await page.getByRole('button', {name:'Memory', exact:true}).click();
  await page.getByLabel('Context block content').fill('Prefer concise replies.');
  await page.getByRole('button', {name:'Save context', exact:true}).click();
  await expect(page.getByRole('button', {name:'profile · r1'})).toBeVisible();
  await page.getByLabel('Context block content').fill('Prefer concise English replies.');
  await page.getByRole('button', {name:'Save context', exact:true}).click();
  await expect(page.getByRole('button', {name:'profile · r2'})).toBeVisible();
  await page.getByLabel('Relation subject').fill('Alice');
  await page.getByLabel('Relation object').fill('Atlas');
  await page.getByRole('button', {name:'Save relationship', exact:true}).click();
  await expect(page.getByText('Alice → works_on → Atlas', {exact:true})).toBeVisible();
});
