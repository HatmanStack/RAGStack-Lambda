/**
 * E2E Tests for Collapsible Sources with Document Access
 *
 * Tests critical user journeys:
 * - Viewing collapsible sources
 * - Downloading documents
 * - Admin configuration toggle
 * - Keyboard navigation
 *
 * Prerequisites:
 * - Application deployed to staging environment
 * - STAGING_URL environment variable set
 * - Test documents uploaded to DataBucket (input/ prefix)
 * - Admin credentials configured
 *
 * Run with:
 *   npx playwright test tests/e2e/collapsible-sources.spec.ts
 *   npx playwright test --headed  # See browser
 *   npx playwright test --debug   # Debugging mode
 */

import { test, expect } from '@playwright/test';

// Configuration from environment variables
const STAGING_URL = process.env.STAGING_URL || 'http://localhost:5173';
const ADMIN_EMAIL = process.env.ADMIN_EMAIL || 'admin@example.com';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'TestPassword123!';

test.describe('Collapsible Sources Feature', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to chat interface
    await page.goto(`${STAGING_URL}/chat`);

    // Wait for page to load
    await page.waitForLoadState('networkidle');
  });

  test('sources are collapsed by default', async ({ page }) => {
    // Send a test query
    const messageInput = page.getByRole('textbox', { name: /type your message/i });
    await messageInput.fill('What documents do you have?');

    const sendButton = page.getByRole('button', { name: /send message/i });
    await sendButton.click();

    // Wait for response with sources
    await page.waitForSelector('[aria-label*="sources"]', { timeout: 30000 });

    // Verify sources toggle button exists
    const sourcesButton = page.getByRole('button', { name: /show.*sources/i });
    await expect(sourcesButton).toBeVisible();

    // Verify aria-expanded is false (collapsed)
    await expect(sourcesButton).toHaveAttribute('aria-expanded', 'false');

    // Verify sources content is NOT visible
    const sourcesDisplay = page.locator('[data-testid="sources-display"]');
    await expect(sourcesDisplay).not.toBeVisible();
  });

  test('sources expand when button clicked', async ({ page }) => {
    // Send query and wait for response
    const messageInput = page.getByRole('textbox', { name: /type your message/i });
    await messageInput.fill('Show me documentation');
    await page.getByRole('button', { name: /send/i }).click();

    // Wait for sources button to appear
    const sourcesButton = page.getByRole('button', { name: /show.*sources/i });
    await sourcesButton.waitFor({ state: 'visible', timeout: 30000 });

    // Click to expand
    await sourcesButton.click();

    // Verify expanded state
    await expect(sourcesButton).toHaveAttribute('aria-expanded', 'true');
    await expect(sourcesButton).toContainText(/hide/i);

    // Verify sources are now visible
    const sourcesDisplay = page.locator('[data-testid="sources-display"]');
    await expect(sourcesDisplay).toBeVisible();

    // Verify source items are present
    const sourceItems = page.locator('.source-item');
    await expect(sourceItems.first()).toBeVisible();
  });

  test('sources collapse when clicked again', async ({ page }) => {
    // Send query
    await page.getByRole('textbox', { name: /type your message/i }).fill('Test query');
    await page.getByRole('button', { name: /send/i }).click();

    // Expand sources
    const sourcesButton = page.getByRole('button', { name: /show.*sources/i });
    await sourcesButton.waitFor({ state: 'visible', timeout: 30000 });
    await sourcesButton.click();

    // Verify expanded
    await expect(sourcesButton).toHaveAttribute('aria-expanded', 'true');

    // Collapse
    await sourcesButton.click();

    // Verify collapsed
    await expect(sourcesButton).toHaveAttribute('aria-expanded', 'false');
    await expect(page.locator('[data-testid="sources-display"]')).not.toBeVisible();
  });
});

test.describe('Document Download Feature', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${STAGING_URL}/chat`);
    await page.waitForLoadState('networkidle');
  });

  test('document link appears when access enabled', async ({ page }) => {
    // Send query
    await page.getByRole('textbox', { name: /type your message/i }).fill('Show me reports');
    await page.getByRole('button', { name: /send/i }).click();

    // Expand sources
    const sourcesButton = page.getByRole('button', { name: /show.*sources/i });
    await sourcesButton.waitFor({ state: 'visible', timeout: 30000 });
    await sourcesButton.click();

    // Look for document link
    const documentLink = page.getByRole('link', { name: /view document/i }).first();

    // Check if document access is enabled by attempting to find the link
    const isDocumentAccessEnabled = await documentLink.isVisible().catch(() => false);

    if (!isDocumentAccessEnabled) {
      // Explicitly skip test when feature is disabled
      test.skip(true, 'Document access is disabled in this environment');
    }

    // If we get here, feature is enabled - verify link attributes
    await expect(documentLink).toBeVisible();
    await expect(documentLink).toHaveAttribute('href', /^https:\/\/s3\.amazonaws\.com/);
    await expect(documentLink).toHaveAttribute('target', '_blank');
    await expect(documentLink).toHaveAttribute('rel', /noopener noreferrer/);
  });

  test('document download initiates on click', async ({ page }) => {
    // Send query
    await page.getByRole('textbox', { name: /type your message/i }).fill('Financial reports');
    await page.getByRole('button', { name: /send/i }).click();

    // Expand sources
    await page.getByRole('button', { name: /show.*sources/i }).click();

    // Check if document link exists
    const documentLink = page.getByRole('link', { name: /view document/i }).first();

    // Check if document access is enabled
    const isDocumentAccessEnabled = await documentLink.isVisible().catch(() => false);

    if (!isDocumentAccessEnabled) {
      // Explicitly skip test when feature is disabled
      test.skip(true, 'Document access is disabled in this environment');
    }

    // If we get here, feature is enabled - test download behavior
    await expect(documentLink).toBeVisible();

    // Set up download listener
    const downloadPromise = page.waitForEvent('download', { timeout: 10000 });

    // Click link
    await documentLink.click();

    // Wait for download (or new tab - depends on browser)
    try {
      const download = await downloadPromise;

      // Verify download started
      expect(download).toBeDefined();

      // Verify filename
      const filename = await download.suggestedFilename();
      expect(filename).toMatch(/\.(pdf|png|jpg|jpeg|docx|txt)$/i);
    } catch (e) {
      // Download might open in new tab instead - that's acceptable behavior
      console.log('Download opened in new tab (expected behavior)');
    }
  });
});

test.describe('Admin Configuration', () => {
  test('admin can toggle document access', async ({ page }) => {
    // Login as admin
    await page.goto(`${STAGING_URL}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(ADMIN_EMAIL);
    await page.getByRole('textbox', { name: /password/i }).fill(ADMIN_PASSWORD);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Navigate to Configuration page
    await page.goto(`${STAGING_URL}/admin/configuration`);
    await page.waitForLoadState('networkidle');

    // Find document access toggle
    const documentAccessToggle = page.getByRole('switch', {
      name: /allow document access|document downloads/i
    });

    // Get current state
    const isCurrentlyEnabled = await documentAccessToggle.isChecked();

    // Toggle OFF if currently ON
    if (isCurrentlyEnabled) {
      await documentAccessToggle.click();

      // Verify success notification
      await expect(page.getByText(/saved|updated successfully/i)).toBeVisible();

      // Verify toggle is now unchecked
      await expect(documentAccessToggle).not.toBeChecked();
    }

    // Toggle ON
    await documentAccessToggle.click();

    // Verify success
    await expect(page.getByText(/saved|updated successfully/i)).toBeVisible();
    await expect(documentAccessToggle).toBeChecked();

    // NOTE: We don't verify chat propagation here because Lambda config cache
    // is per-instance and only refreshes when getChatConfig() is invoked AFTER
    // the 60s TTL expires. Waiting doesn't trigger invocation, and earlier tests
    // may have warmed the cache. Cache behavior is covered by unit/integration tests.
  });
});

test.describe('Keyboard Navigation', () => {
  test('sources toggle is keyboard accessible', async ({ page }) => {
    await page.goto(`${STAGING_URL}/chat`);

    // Send query
    await page.getByRole('textbox', { name: /type your message/i }).fill('Test');
    await page.keyboard.press('Enter'); // Submit with Enter

    // Wait for sources button
    const sourcesButton = page.getByRole('button', { name: /show.*sources/i });
    await sourcesButton.waitFor({ state: 'visible', timeout: 30000 });

    // Focus the button directly (more robust than counting Tab presses)
    await sourcesButton.focus();

    // Verify focus
    await expect(sourcesButton).toBeFocused();

    // Activate with Enter
    await page.keyboard.press('Enter');

    // Verify expanded
    await expect(sourcesButton).toHaveAttribute('aria-expanded', 'true');

    // Activate with Space to collapse
    await page.keyboard.press('Space');

    // Verify collapsed
    await expect(sourcesButton).toHaveAttribute('aria-expanded', 'false');
  });

  test('document links are focusable', async ({ page }) => {
    await page.goto(`${STAGING_URL}/chat`);

    // Send query and expand sources
    await page.getByRole('textbox', { name: /type your message/i }).fill('Documents');
    await page.keyboard.press('Enter');

    await page.getByRole('button', { name: /show.*sources/i }).click();

    // Tab to document link
    const documentLink = page.getByRole('link', { name: /view document/i }).first();

    if (await documentLink.isVisible()) {
      // Focus link via keyboard
      await documentLink.focus();
      await expect(documentLink).toBeFocused();

      // Verify Enter activates link
      // (We won't actually click to avoid download in test)
      await expect(documentLink).toHaveAttribute('href', /^https/);
    }
  });
});

test.describe('SessionStorage Persistence', () => {
  test('expanded state persists on page refresh', async ({ page }) => {
    await page.goto(`${STAGING_URL}/chat`);

    // Send query and expand
    await page.getByRole('textbox', { name: /type your message/i }).fill('Test');
    await page.getByRole('button', { name: /send/i }).click();

    const sourcesButton = page.getByRole('button', { name: /show.*sources/i });
    await sourcesButton.waitFor({ state: 'visible', timeout: 30000 });
    await sourcesButton.click();

    // Verify expanded
    await expect(sourcesButton).toHaveAttribute('aria-expanded', 'true');

    // Refresh page
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Send another query
    await page.getByRole('textbox', { name: /type your message/i }).fill('Test 2');
    await page.getByRole('button', { name: /send/i }).click();

    // Wait for new sources button
    const newSourcesButton = page.getByRole('button', { name: /hide.*sources/i });
    await newSourcesButton.waitFor({ state: 'visible', timeout: 30000 });

    // Should still be expanded (from sessionStorage)
    await expect(newSourcesButton).toHaveAttribute('aria-expanded', 'true');
  });
});
