import { test, expect } from '@playwright/test';

test('app renders without crashing', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await expect(page.getByText('Trading Opportunity Scanner')).toBeVisible();
});

test('scan template selector renders', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await expect(page.getByText('Scan Templates')).toBeVisible();
});

test('run scan button is disabled when no template selected', async ({ page }) => {
  await page.goto('http://localhost:5173');
  const button = page.getByRole('button', { name: 'Run Scan' });
  await expect(button).toBeDisabled();
});
