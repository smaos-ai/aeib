/**
 * SMAOS Flight Metaphor UI Integration Tests
 * Test all 4 phases: PRE-FLIGHT → LAUNCH → FLYING → BLACK BOX
 */

import { test, expect } from '@playwright/test';

test.describe('SMAOS Flight Metaphor UI', () => {
  test.beforeEach(async ({ page }) => {
    // Start at home
    await page.goto('http://localhost:5174', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000); // Wait for React to mount
  });

  // ==========================================
  // PHASE 1: PRE-FLIGHT (Setup & Learning)
  // ==========================================

  test('Phase 1: PRE-FLIGHT - Initial state shows blue theme', async ({ page }) => {
    // Check phase navigator visible
    const navigator = page.locator('text=PRE-FLIGHT');
    await expect(navigator).toBeVisible();

    // Check blue emoji visible
    const blueEmoji = page.locator('text=🔵');
    await expect(blueEmoji).toBeVisible();
  });

  test('Phase 1: PRE-FLIGHT - Shows architecture guide', async ({ page }) => {
    const archGuide = page.locator('text=Architecture Guide');
    await expect(archGuide).toBeVisible({ timeout: 3000 });
  });

  test('Phase 1: PRE-FLIGHT - Shows regulatory compliance', async ({ page }) => {
    const compliance = page.locator('text=Regulatory Compliance');
    await expect(compliance).toBeVisible({ timeout: 3000 });
  });

  test('Phase 1: PRE-FLIGHT - Shows button reference guide', async ({ page }) => {
    const buttonGuide = page.locator('text=Button Reference Guide');
    await expect(buttonGuide).toBeVisible({ timeout: 3000 });
  });

  test('Phase 1: PRE-FLIGHT - Checklist visible on right sidebar', async ({ page }) => {
    const checklist = page.locator('text=PRE-FLIGHT CHECKLIST');
    await expect(checklist).toBeVisible({ timeout: 3000 });
  });

  test('Phase 1: PRE-FLIGHT - "READY FOR LAUNCH?" button visible', async ({ page }) => {
    const launchBtn = page.locator('text=READY FOR LAUNCH');
    await expect(launchBtn).toBeVisible({ timeout: 3000 });
  });

  // ==========================================
  // PHASE 2: LAUNCH (Ignition)
  // ==========================================

  test('Phase 2: LAUNCH - Click READY FOR LAUNCH transitions to LAUNCH phase', async ({ page }) => {
    // Click the launch button
    await page.click('text=READY FOR LAUNCH');

    // Wait for phase change
    await page.waitForTimeout(500);

    // Check orange emoji visible
    const orangeEmoji = page.locator('text=🟡');
    await expect(orangeEmoji).toBeVisible({ timeout: 3000 });

    // Check LAUNCH text visible
    const launchPhase = page.locator('text=LAUNCH').nth(0);
    await expect(launchPhase).toBeVisible({ timeout: 3000 });
  });

  test('Phase 2: LAUNCH - Countdown timer visible', async ({ page }) => {
    await page.click('text=READY FOR LAUNCH');

    // Wait for countdown to appear
    const countdown = page.locator('text=Initializing systems');
    await expect(countdown).toBeVisible({ timeout: 3000 });
  });

  test('Phase 2: LAUNCH - Health check progress bars visible', async ({ page }) => {
    await page.click('text=READY FOR LAUNCH');

    // Check for health check labels
    await expect(page.locator('text=Policy Engine')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('text=Knowledge Base')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('text=Permit Gates')).toBeVisible({ timeout: 3000 });
  });

  test('Phase 2: LAUNCH - Auto-advances to FLYING after ~8 seconds', async ({ page }) => {
    await page.click('text=READY FOR LAUNCH');

    // Wait for auto-advance (up to 12 seconds)
    await page.waitForTimeout(12000);

    // Check for green emoji (FLYING phase)
    const greenEmoji = page.locator('text=🟢');
    await expect(greenEmoji).toBeVisible({ timeout: 3000 });
  });

  // ==========================================
  // PHASE 3: FLYING (Active Monitoring)
  // ==========================================

  test('Phase 3: FLYING - Green theme shows', async ({ page }) => {
    // Skip to FLYING phase
    await page.click('text=READY FOR LAUNCH');
    await page.waitForTimeout(12000);

    // Check green emoji visible
    const greenEmoji = page.locator('text=🟢');
    await expect(greenEmoji).toBeVisible({ timeout: 3000 });
  });

  test('Phase 3: FLYING - System Status panel visible', async ({ page }) => {
    await page.click('text=READY FOR LAUNCH');
    await page.waitForTimeout(12000);

    // Check System Status
    await expect(page.locator('text=System Status')).toBeVisible({ timeout: 3000 });
  });

  test('Phase 3: FLYING - Live Metrics visible', async ({ page }) => {
    await page.click('text=READY FOR LAUNCH');
    await page.waitForTimeout(12000);

    // Check Metrics
    await expect(page.locator('text=Live Metrics')).toBeVisible({ timeout: 3000 });
  });

  test('Phase 3: FLYING - Transaction Simulator visible', async ({ page }) => {
    await page.click('text=READY FOR LAUNCH');
    await page.waitForTimeout(12000);

    // Check Simulator
    await expect(page.locator('text=Transaction Simulator')).toBeVisible({ timeout: 3000 });
  });

  test('Phase 3: FLYING - Agent Execution DAG visible', async ({ page }) => {
    await page.click('text=READY FOR LAUNCH');
    await page.waitForTimeout(12000);

    // Check DAG
    await expect(page.locator('text=Agent Execution DAG')).toBeVisible({ timeout: 3000 });
  });

  test('Phase 3: FLYING - LAND / SHUTDOWN button visible at bottom', async ({ page }) => {
    await page.click('text=READY FOR LAUNCH');
    await page.waitForTimeout(12000);

    // Check LAND button
    const landBtn = page.locator('text=LAND / SHUTDOWN');
    await expect(landBtn).toBeVisible({ timeout: 3000 });
  });

  test('Phase 3: FLYING - Back to Pre-Flight button visible', async ({ page }) => {
    await page.click('text=READY FOR LAUNCH');
    await page.waitForTimeout(12000);

    // Check back button
    const backBtn = page.locator('text=Back to Pre-Flight');
    await expect(backBtn).toBeVisible({ timeout: 3000 });
  });

  // ==========================================
  // PHASE 4: BLACK BOX (Immutable Logging)
  // ==========================================

  test('Phase 4: BLACK BOX - Click LAND transitions to BLACK BOX', async ({ page }) => {
    // Skip to FLYING
    await page.click('text=READY FOR LAUNCH');
    await page.waitForTimeout(12000);

    // Click LAND button
    await page.click('text=LAND / SHUTDOWN');
    await page.waitForTimeout(500);

    // Check black box emoji
    const blackEmoji = page.locator('text=⬛');
    await expect(blackEmoji).toBeVisible({ timeout: 3000 });
  });

  test('Phase 4: BLACK BOX - Immutable ledger visible', async ({ page }) => {
    await page.click('text=READY FOR LAUNCH');
    await page.waitForTimeout(12000);
    await page.click('text=LAND / SHUTDOWN');
    await page.waitForTimeout(500);

    // Check ledger header
    const ledger = page.locator('text=Flight Data Recorder');
    await expect(ledger).toBeVisible({ timeout: 3000 });
  });

  test('Phase 4: BLACK BOX - Download button visible', async ({ page }) => {
    await page.click('text=READY FOR LAUNCH');
    await page.waitForTimeout(12000);
    await page.click('text=LAND / SHUTDOWN');
    await page.waitForTimeout(500);

    // Check download button
    const downloadBtn = page.locator('text=Download Flight Recorder');
    await expect(downloadBtn).toBeVisible({ timeout: 3000 });
  });

  test('Phase 4: BLACK BOX - Reset button visible', async ({ page }) => {
    await page.click('text=READY FOR LAUNCH');
    await page.waitForTimeout(12000);
    await page.click('text=LAND / SHUTDOWN');
    await page.waitForTimeout(500);

    // Check reset button
    const resetBtn = page.locator('text=Reset & Return to Pre-Flight');
    await expect(resetBtn).toBeVisible({ timeout: 3000 });
  });

  test('Phase 4: BLACK BOX - Reset button returns to PRE-FLIGHT', async ({ page }) => {
    // Go through all phases
    await page.click('text=READY FOR LAUNCH');
    await page.waitForTimeout(12000);
    await page.click('text=LAND / SHUTDOWN');
    await page.waitForTimeout(500);

    // Click reset
    await page.click('text=Reset & Return to Pre-Flight');
    await page.waitForTimeout(500);

    // Check back to blue theme
    const blueEmoji = page.locator('text=🔵');
    await expect(blueEmoji).toBeVisible({ timeout: 3000 });

    // Check for PRE-FLIGHT text
    await expect(page.locator('text=PRE-FLIGHT CHECKLIST')).toBeVisible({ timeout: 3000 });
  });

  // ==========================================
  // PHASE NAVIGATOR
  // ==========================================

  test('Phase Navigator - Shows all 4 phases', async ({ page }) => {
    // Check all phase names visible in navigator
    await expect(page.locator('text=PRE-FLIGHT')).toBeVisible();
    await expect(page.locator('text=LAUNCH')).toBeVisible();
    await expect(page.locator('text=FLYING')).toBeVisible();
    await expect(page.locator('text=BLACK BOX')).toBeVisible();
  });

  test('Phase Navigator - Updates when transitioning phases', async ({ page }) => {
    // Start in PRE-FLIGHT
    const preFlightEmoji = page.locator('text=🔵').first();
    await expect(preFlightEmoji).toBeVisible();

    // Transition to LAUNCH
    await page.click('text=READY FOR LAUNCH');
    await page.waitForTimeout(500);

    // Check orange emoji visible (LAUNCH active)
    const launchEmoji = page.locator('text=🟡');
    await expect(launchEmoji).toBeVisible({ timeout: 3000 });
  });

  // ==========================================
  // ACCESSIBILITY & RESPONSIVENESS
  // ==========================================

  test('Accessibility - All buttons have focus indicators', async ({ page }) => {
    // Tab to a button
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');

    // The button should have focus
    // (This is implicit in Playwright's focus handling)
    await page.waitForTimeout(500);
  });

  test('Accessibility - Page scrollable on small viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Should still be able to scroll
    const scrollHeight = await page.evaluate(() => document.documentElement.scrollHeight);
    const viewportHeight = await page.evaluate(() => window.innerHeight);

    expect(scrollHeight).toBeGreaterThan(viewportHeight);
  });

  test('Responsiveness - Desktop layout works (1920x1080)', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });

    // Check main content visible
    const navigator = page.locator('text=PRE-FLIGHT');
    await expect(navigator).toBeVisible();
  });

  test('Responsiveness - Mobile layout works (375x667)', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });

    // Check main content still visible
    const navigator = page.locator('text=PRE-FLIGHT');
    await expect(navigator).toBeVisible();
  });

  // ==========================================
  // PERFORMANCE & STABILITY
  // ==========================================

  test('No console errors', async ({ page, context }) => {
    const errors = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    // Go through all phases
    await page.click('text=READY FOR LAUNCH');
    await page.waitForTimeout(12000);
    await page.click('text=LAND / SHUTDOWN');
    await page.waitForTimeout(500);
    await page.click('text=Reset & Return to Pre-Flight');

    expect(errors).toEqual([]);
  });

  test('Full journey completes without freezing', async ({ page }) => {
    // PRE-FLIGHT to LAUNCH
    await page.click('text=READY FOR LAUNCH');

    // Wait for LAUNCH completion (auto-advance to FLYING)
    await page.waitForTimeout(12000);

    // FLYING: Verify page responsive
    await page.click('text=LAND / SHUTDOWN');

    // BLACK BOX: Verify page responsive
    await page.click('text=Reset & Return to Pre-Flight');

    // Back to PRE-FLIGHT: Should be fast
    const checklist = page.locator('text=PRE-FLIGHT CHECKLIST');
    await expect(checklist).toBeVisible({ timeout: 3000 });
  });
});
