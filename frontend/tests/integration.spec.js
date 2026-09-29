import { test, expect } from '@playwright/test';
const password = process.env.DEMO_PASSWORD;
const apiOrigin = process.env.E2E_BASE_URL;
function response(page, method, path) {
  return page.waitForResponse(
    (r) => r.request().method() === method && new URL(r.url()).pathname === '/api/v1' + path,
  );
}
async function login(page, email) {
  await page.goto('/sign-in');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  const pending = response(page, 'POST', '/auth/login');
  await page.getByRole('button', { name: 'Login', exact: true }).click();
  expect((await pending).status()).toBe(200);
}
async function logout(page) {
  await page.getByRole('button', { name: 'Open profile menu' }).click();
  const pending = response(page, 'POST', '/auth/logout');
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  expect((await pending).status()).toBe(200);
  await expect(page).toHaveURL(/sign-in/);
}
test('real cookie session → product → OCR → Python/GTM → reviewer decision', async ({
  page,
  context,
}, testInfo) => {
  expect(password, 'Run with the real-stack harness and seeded password').toBeTruthy();
  expect(apiOrigin).toBeTruthy();
  const errors = [];
  const traffic = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('response', (r) => {
    if (r.url().includes('/api/v1/'))
      traffic.push({
        method: r.request().method(),
        path: new URL(r.url()).pathname,
        status: r.status(),
      });
  });
  const unique = Date.now();
  const email = `browser-${unique}@example.com`;
  await page.goto('/register');
  await page.getByLabel('Full name').fill('Browser Customer');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  const register = response(page, 'POST', '/auth/register');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  expect((await register).status()).toBe(201);
  await expect(page).toHaveURL(/overview/);
  await expect(page.getByRole('heading', { name: 'Product coverage', exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('dashboard-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('button', { name: 'Toggle navigation' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.screenshot({ path: testInfo.outputPath('dashboard-mobile.png'), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1100 });
  await logout(page);
  await login(page, email);
  await expect(page).toHaveURL(/overview/);
  const cookies = await context.cookies(apiOrigin + '/api/v1/me');
  expect(cookies.find((c) => c.name === 'assurex_session')?.httpOnly).toBe(true);
  const me = response(page, 'GET', '/me');
  await page.reload();
  expect((await me).status()).toBe(200);
  await expect(page).toHaveURL(/overview/);
  await page.goto('/products/new');
  await page.getByLabel('Product name', { exact: true }).fill('Browser mobile');
  await page.getByLabel('Retailer', { exact: true }).fill('Test retailer');
  await page.getByLabel('Brand', { exact: true }).fill('BrowserBrand');
  await page.getByLabel('Model', { exact: true }).fill('M1');
  await page.getByLabel('Serial number', { exact: true }).fill('BROWSER123');
  await page.getByLabel('Purchase date').fill(process.env.TEST_PURCHASE_DATE);
  await page.getByLabel('Purchase amount').fill('899.00');
  const created = response(page, 'POST', '/products');
  await page.getByRole('button', { name: 'Save product' }).click();
  const productResponse = await created;
  expect(productResponse.status()).toBe(201);
  const product = (await productResponse.json()).data;
  await page.getByRole('link', { name: 'Edit warranty' }).click();
  await page.getByLabel('Warranty provider').fill('Browser Warranty');
  await page.getByLabel('Warranty policy').selectOption('mobile-1.0');
  await page.getByLabel('Coverage start').fill(process.env.TEST_PURCHASE_DATE);
  await page.getByLabel('Coverage expiry').fill(process.env.TEST_EXPIRY_DATE);
  const warranty = response(page, 'PATCH', `/products/${product.id}/warranty`);
  await page.getByRole('button', { name: 'Save warranty' }).click();
  expect((await warranty).status()).toBe(200);
  await page.getByRole('link', { name: 'Start claim' }).click();
  await page.getByLabel('Product', { exact: true }).selectOption(product.id);
  await page.getByRole('button', { name: 'Continue to issue' }).click();
  await page.getByLabel('Fault date').fill(process.env.TEST_FAULT_DATE);
  await page.getByLabel('Fault category').selectOption('display');
  await page.getByLabel('Damage type').selectOption('none');
  await page.getByLabel('Serial number', { exact: true }).fill('BROWSER123');
  await page.getByLabel('Invoice number', { exact: true }).fill('BROWSERINV');
  await page.getByLabel('Fault description').fill('The display stopped working.');
  const createdClaim = response(page, 'POST', '/claims');
  await page.getByRole('button', { name: 'Save claim draft' }).click();
  const claimResponse = await createdClaim;
  expect(claimResponse.status()).toBe(201);
  const claim = (await claimResponse.json()).data;
  for (const kind of ['receipt', 'serial_photo']) {
    await page.getByLabel('Document type', { exact: true }).selectOption(kind);
    await page.getByLabel('Evidence file').setInputFiles(process.env.TEST_RECEIPT);
    const upload = response(page, 'POST', `/claims/${claim.id}/documents`);
    await page.getByRole('button', { name: 'Upload document', exact: true }).click();
    expect((await upload).status()).toBe(202);
    const document = page
      .getByTestId('document')
      .filter({ has: page.getByRole('heading', { name: new RegExp(kind) }) });
    await expect(document.getByTestId('job-progress')).toContainText('completed', {
      timeout: 90000,
    });
    await expect(document.locator('.source-preview')).toBeVisible();
    await expect
      .poll(() =>
        document.locator('.source-preview').evaluate((img) => img.complete && img.naturalWidth > 0),
      )
      .toBe(true);
    for (const field of ['purchase_date', 'serial', 'invoice_number']) {
      const row = document.getByTestId(`ocr-${field}`);
      await expect(row).toBeVisible();
      await row.getByRole('button', {name:'Correct details'}).click();
      const value = {
        purchase_date: process.env.TEST_PURCHASE_DATE,
        serial: 'BROWSER123',
        invoice_number: 'BROWSERINV',
      }[field];
      await row.getByRole('textbox').fill(value);
      const correction = page.waitForResponse(
        (r) => r.request().method() === 'PATCH' && r.url().includes('/ocr-fields/'),
      );
      await row.getByRole('button', { name: 'Confirm / correct' }).click();
      expect((await correction).status()).toBe(200);
      await expect(row).toContainText('Confirmed/corrected');
    }
  }
  await page.reload();
  await expect(page.getByTestId('document')).toHaveCount(2);
  const submitted = response(page, 'POST', `/claims/${claim.id}/submit`);
  await page.getByRole('button', { name: 'Submit claim', exact: true }).click();
  const submission = await submitted;
  expect(submission.status()).toBe(202);
  expect(submission.request().headers()['idempotency-key'].length).toBeGreaterThanOrEqual(8);
  expect(submission.request().headers()['x-csrf-token']).toBeTruthy();
  await expect(page.getByTestId('evaluation')).toBeVisible({ timeout: 120000 });
  const apiResult = await context.request.get(`${apiOrigin}/api/v1/claims/${claim.id}/evaluations`);
  expect(apiResult.status()).toBe(200);
  const evaluation = (await apiResult.json()).data.at(-1);
  expect(evaluation.predictions.python).not.toBeNull();
  expect(evaluation.predictions.gtm).not.toBeNull();
  expect(evaluation.model_errors).toEqual({});
  await expect(page.getByTestId('recommendation')).toHaveText(evaluation.recommendation);
  for (const family of ['python', 'gtm'])
    for (const label of ['valid', 'invalid', 'manual_review'])
      await expect(page.getByTestId(`${family}-${label}`)).toContainText(
        (evaluation.predictions[family][label] * 100).toFixed(2) + '%',
      );
  await page.screenshot({ path: testInfo.outputPath('customer-evaluation.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.screenshot({ path: testInfo.outputPath('claim-mobile.png'), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1100 });
  await logout(page);
  await login(page, 'reviewer@example.com');
  await page.goto(`/review/${claim.id}`);
  await page.getByLabel('Decision', { exact: true }).selectOption('approve');
  await page
    .getByLabel('Decision reason')
    .fill('Evidence verified in real browser integration test.');
  const reviewed = response(page, 'POST', `/claims/${claim.id}/reviews`);
  await page.getByRole('button', { name: 'Save decision' }).click();
  await page.getByRole('button', { name: 'Confirm decision' }).click();
  const reviewResponse = await reviewed;
  expect(reviewResponse.status()).toBe(201);
  const review = (await reviewResponse.json()).data;
  expect(review.after).toBe('Approved');
  expect(review.reason).toContain('real browser');
  await expect(page.locator('.page-header')).toContainText('Approved');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download PDF report' }).click();
  expect((await download).suggestedFilename()).toContain('.pdf');
  await page.screenshot({ path: testInfo.outputPath('reviewer-approved.png'), fullPage: true });
  await expect(
    page.getByText('Evidence verified in real browser integration test.', { exact: true }),
  ).toBeVisible();
  await logout(page);
  await login(page, 'admin@example.com');
  for (const [path, heading] of [
    ['policies', 'Policies'],
    ['models', 'Model registry'],
    ['people', 'People'],
    ['assignments', 'Reviewer assignments'],
    ['audit', 'Audit log'],
  ]) {
    await page.goto(`/admin/${path}`);
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    await expect(page.getByText('Request failed')).toHaveCount(0);
  }
  await page.goto('/account');
  await page.getByLabel('Full name').fill('Browser Administrator');
  const profile = response(page, 'PATCH', '/me');
  await page.getByRole('button', { name: 'Save profile' }).click();
  expect((await profile).status()).toBe(200);
  await expect(page.getByText('Profile saved.')).toBeVisible();
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => localStorage.getItem('assurex-frontend-v2'))).toBeNull();
  await testInfo.attach('real-network-contracts', {
    body: JSON.stringify({ traffic, evaluationId: evaluation.id, reviewId: review.id }, null, 2),
    contentType: 'application/json',
  });
});
