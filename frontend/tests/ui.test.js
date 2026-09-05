import { test, expect } from '@playwright/test'

test('SMAOS - Every Button Works', async ({ page }) => {
  await page.goto('http://127.0.0.1:5173')
  
  // Page loads
  await expect(page.locator('text=Governance Framework')).toBeVisible()
  
  // Capsule selector works
  await page.selectOption('select', 'treasuryBaselIII')
  
  // Form inputs work
  const inputs = page.locator('input')
  await inputs.first().fill('Goldman Sachs')
  await inputs.nth(1).fill('50000000')
  
  // Risk classification triggers
  await page.waitForTimeout(300)
  await expect(page.locator('text=HIGH-RISK')).toBeVisible()
  
  // Submit button works
  await page.click('button:has-text("Send to Work Surface")')
  await page.waitForTimeout(1000)
  
  // Veto card appears
  await expect(page.locator('text=EXECUTION BLOCKED')).toBeVisible()
  
  // Authorize button works
  await page.click('button:has-text("Authorize")')
  await page.waitForTimeout(500)
  
  // Receipt appears
  await expect(page.locator('text=VETO.AUTHORIZE')).toBeVisible()
  
  console.log('✅ ALL BUTTONS WORK')
})
