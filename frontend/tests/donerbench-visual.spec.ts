import { expect, test } from '@playwright/test';

test('renders nonblank Three.js simulation canvases', async ({ page }, testInfo) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Run Benchmark' }).click();

  const canvases = page.locator('canvas');
  await expect(canvases.first()).toBeVisible();
  await expect.poll(async () => canvases.count(), { timeout: 10_000 }).toBeGreaterThanOrEqual(1);

  await page.waitForTimeout(600);

  const nonblankCanvases = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('canvas')).filter((canvas) => {
      const context = canvas.getContext('webgl2') || canvas.getContext('webgl');
      if (!context || canvas.width === 0 || canvas.height === 0) return false;
      const width = Math.min(canvas.width, 240);
      const height = Math.min(canvas.height, 180);
      const sample = new Uint8Array(width * height * 4);
      context.readPixels(0, 0, width, height, context.RGBA, context.UNSIGNED_BYTE, sample);
      let litPixels = 0;
      for (let i = 0; i < sample.length; i += 4) {
        if (sample[i] + sample[i + 1] + sample[i + 2] > 48) litPixels += 1;
      }
      return litPixels > width * height * 0.08;
    }).length;
  });

  expect(nonblankCanvases).toBeGreaterThanOrEqual(1);
  await page.screenshot({
    path: testInfo.outputPath(`donerbench-${testInfo.project.name}.png`),
    fullPage: true
  });
});
