import { test } from '@playwright/test'

test('Debug page load', async ({ page }) => {
  await page.goto('http://127.0.0.1:5173')
  await page.waitForTimeout(3000)
  
  console.log('\n===== PAGE TITLE =====')
  console.log(await page.title())
  
  console.log('\n===== PAGE TEXT =====')
  const text = await page.evaluate(() => document.body.innerText)
  console.log(text.substring(0, 500))
  
  console.log('\n===== CHECKING FOR APP ELEMENTS =====')
  const hasGovernance = await page.locator(':text("Governance")').count()
  console.log('Governance elements:', hasGovernance)
  
  const inputCount = await page.locator('input').count()
  console.log('Input elements:', inputCount)
  
  const buttonCount = await page.locator('button').count()
  console.log('Button elements:', buttonCount)
  
  console.log('\n===== CHECKING FOR ERRORS =====')
  const consoleMessages = []
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleMessages.push(msg.text())
    }
  })
  
  await page.waitForTimeout(1000)
  console.log('Console errors:', consoleMessages.length)
  consoleMessages.forEach(err => console.log('  -', err))
})
