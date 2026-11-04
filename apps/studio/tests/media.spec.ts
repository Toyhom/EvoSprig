import { test, expect } from '@playwright/test';

test('review and result panels preview selected media without loading it in the background', async ({ page, request }) => {
  const id = 'media-review-' + Date.now().toString(36);
  const image = { id: 'frame', uri: 'https://media.example.test/frame.png', media_type: 'image/png' };
  const video = { id: 'clip', uri: 'https://media.example.test/clip.mp4', media_type: 'video/mp4' };
  let imageRequests = 0;
  await page.route(image.uri, route => {
    imageRequests++;
    return route.fulfill({ contentType: 'image/png', body: Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64') });
  });
  const spec = {
    spec_version: '0.3', id, input_schema: { type: 'object' }, output_schema: {}, models: {}, tools: {}, resources: {},
    graph: { entry: 'review', nodes: { review: { type: 'human', output_schema: { type: 'object' }, inputs: {
      takes: { value: [image, image, {frame:image,clip:video}, { ...image, uri: 'javascript:alert(1)' }, { ...image, uri: 'file:///private.png' }] }
    } } }, edges: [], output: { selection: { ref: 'nodes.review.output' } } }
  };
  expect((await request.post('/api/projects', { data: { spec } })).status()).toBe(201);
  await page.goto('/');
  await page.locator('.project[title="' + id + '"]').click();
  await page.getByRole('button', { name: '▷ Run', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Show media · 2' })).toBeVisible();
  expect(imageRequests).toBe(0);
  await expect(page.locator('.media-grid')).toHaveCount(0);
  await page.getByRole('button', { name: 'Show media · 2' }).click();
  await expect(page.locator('.media-grid img')).toHaveCount(1);
  await expect.poll(() => imageRequests).toBe(1);
  await expect(page.locator('.media-grid video')).toHaveAttribute('preload', 'none');
  await expect(page.locator('.media-grid video')).toHaveAttribute('poster', image.uri);
  await expect(page.locator('.media-grid video')).not.toHaveAttribute('autoplay');
  await expect(page.locator('.media-grid a')).toHaveCount(2);
  await page.getByLabel('Your response', { exact: true }).fill(JSON.stringify({ frame: image }));
  await page.getByRole('button', { name: 'Submit and continue', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('succeeded');
  await page.getByRole('button', { name: 'Show media · 1' }).click();
  await expect(page.locator('.media-grid img')).toHaveCount(1);
});
