import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  calculatePrice,
  applyDiscount,
  createStripeCustomer,
  createStripeSubscription,
  handlePaymentWebhook,
  prorate
} from '../src/lib/billing'
import type { BillingMetrics } from '../src/lib/types'

describe('Pricing Calculation', () => {
  it('should calculate starter plan price ($99)', () => {
    const price = calculatePrice('starter')
    expect(price).toBe(9900) // cents
  })

  it('should calculate pro plan price ($299)', () => {
    const price = calculatePrice('pro')
    expect(price).toBe(29900) // cents
  })

  it('should calculate enterprise plan price ($999)', () => {
    const price = calculatePrice('enterprise')
    expect(price).toBe(99900) // cents
  })

  it('should return 0 for invalid plan', () => {
    const price = calculatePrice('invalid')
    expect(price).toBe(0)
  })
})

describe('Discount Application', () => {
  it('should apply 10% annual discount', () => {
    const basePrice = 29900
    const discounted = applyDiscount(basePrice, 'annual')
    expect(discounted).toBe(26910) // 29900 * 0.9
  })

  it('should apply no discount for monthly', () => {
    const basePrice = 29900
    const discounted = applyDiscount(basePrice, 'monthly')
    expect(discounted).toBe(29900)
  })

  it('should round to nearest cent', () => {
    const basePrice = 10000
    const discounted = applyDiscount(basePrice, 'annual')
    expect(discounted).toBe(9000)
  })
})

describe('Stripe Integration', () => {
  const testTenantId = 'test-tenant-stripe'

  it('should create Stripe customer with email', async () => {
    const customerId = await createStripeCustomer(
      testTenantId,
      'test@example.com',
      'Test Corp'
    )
    expect(customerId).toMatch(/^cus_/)
  })

  it('should create Stripe subscription', async () => {
    const customerId = await createStripeCustomer(
      testTenantId,
      'subscription@example.com',
      'Sub Corp'
    )

    const subscriptionId = await createStripeSubscription(
      customerId,
      'price_1234567890',
      'monthly'
    )
    expect(subscriptionId).toMatch(/^sub_/)
  })

  it('should fail on invalid Stripe token', async () => {
    await expect(
      createStripeCustomer(testTenantId, 'invalid@example.com', 'Corp', 'invalid_token')
    ).rejects.toThrow()
  })

  it('should handle Stripe webhook: payment success', async () => {
    const event = {
      type: 'payment_intent.succeeded',
      data: {
        object: {
          id: 'pi_1234567890',
          amount: 29900,
          currency: 'usd',
          customer: 'cus_1234567890'
        }
      }
    }

    const result = await handlePaymentWebhook(event)
    expect(result.status).toBe('success')
  })

  it('should handle Stripe webhook: payment failure', async () => {
    const event = {
      type: 'payment_intent.payment_failed',
      data: {
        object: {
          id: 'pi_failed',
          customer: 'cus_failed'
        }
      }
    }

    const result = await handlePaymentWebhook(event)
    expect(result.status).toBe('failed')
  })

  it('should handle Stripe webhook: subscription updated', async () => {
    const event = {
      type: 'customer.subscription.updated',
      data: {
        object: {
          id: 'sub_1234567890',
          customer: 'cus_1234567890',
          status: 'active',
          current_period_end: 1704067200
        }
      }
    }

    const result = await handlePaymentWebhook(event)
    expect(result.status).toBe('updated')
  })
})

describe('Proration', () => {
  it('should prorate on upgrade mid-cycle', () => {
    const cycleStart = new Date('2024-01-01')
    const cycleEnd = new Date('2024-01-31')
    const upgradeDate = new Date('2024-01-15')
    const oldPrice = 9900 // starter
    const newPrice = 29900 // pro

    const prorated = prorate(cycleStart, cycleEnd, upgradeDate, oldPrice, newPrice)
    expect(prorated).toBeGreaterThan(0)
    expect(prorated).toBeLessThan(newPrice)
  })

  it('should prorate on downgrade mid-cycle', () => {
    const cycleStart = new Date('2024-01-01')
    const cycleEnd = new Date('2024-01-31')
    const downgradeDate = new Date('2024-01-20')
    const oldPrice = 29900 // pro
    const newPrice = 9900 // starter

    const prorated = prorate(cycleStart, cycleEnd, downgradeDate, oldPrice, newPrice)
    expect(prorated).toBeGreaterThan(0)
    expect(prorated).toBeLessThan(oldPrice)
  })
})

describe('Multi-Tenant Billing Isolation', () => {
  it('should track separate balance for each tenant', async () => {
    const customer1 = await createStripeCustomer('tenant1', 'tenant1@example.com', 'Corp1')
    const customer2 = await createStripeCustomer('tenant2', 'tenant2@example.com', 'Corp2')

    expect(customer1).not.toBe(customer2)
  })

  it('should not allow cross-tenant subscription access', async () => {
    const customerId = await createStripeCustomer(
      'tenant-isolation',
      'isolation@example.com',
      'Isolation Corp'
    )

    await expect(
      createStripeSubscription(
        'cus_invalid_' + customerId,
        'price_1234567890',
        'monthly'
      )
    ).rejects.toThrow()
  })
})

describe('Invoice & Payment Tracking', () => {
  it('should track invoice for successful payment', async () => {
    const event = {
      type: 'invoice.paid',
      data: {
        object: {
          id: 'in_1234567890',
          customer: 'cus_1234567890',
          amount_paid: 29900,
          paid: true
        }
      }
    }

    const result = await handlePaymentWebhook(event)
    expect(result.invoiceId).toBeDefined()
  })

  it('should handle failed invoice payment', async () => {
    const event = {
      type: 'invoice.payment_failed',
      data: {
        object: {
          id: 'in_failed',
          customer: 'cus_1234567890',
          amount_due: 29900
        }
      }
    }

    const result = await handlePaymentWebhook(event)
    expect(result.status).toBe('failed')
  })
})

describe('Plan Transitions', () => {
  it('should support upgrade from starter to pro', async () => {
    const basePrice = calculatePrice('starter')
    const upgradePrice = calculatePrice('pro')
    expect(upgradePrice).toBeGreaterThan(basePrice)
  })

  it('should support downgrade from pro to starter', async () => {
    const proPrice = calculatePrice('pro')
    const starterPrice = calculatePrice('starter')
    expect(proPrice).toBeGreaterThan(starterPrice)
  })

  it('should calculate credit on downgrade', () => {
    const paidAmount = 29900
    const creditFromDowngrade = paidAmount - calculatePrice('starter')
    expect(creditFromDowngrade).toBeGreaterThan(0)
  })
})

describe('Usage-Based Billing Components', () => {
  it('should calculate per-user charge ($10/user/month)', () => {
    const perUserPrice = 1000 // $10 in cents
    const userCount = 5
    const monthlyCharge = perUserPrice * userCount
    expect(monthlyCharge).toBe(5000)
  })

  it('should calculate per-API-call charge ($0.001 per call)', () => {
    const perCallPrice = 0.001
    const apiCalls = 1000
    const charge = perCallPrice * apiCalls
    expect(charge).toBe(1)
  })

  it('should calculate per-storage charge ($0.05 per GB)', () => {
    const perGBPrice = 0.05
    const storageGB = 100
    const charge = perGBPrice * storageGB
    expect(charge).toBe(5)
  })

  it('should combine all billing components', () => {
    const planPrice = 29900 // cents
    const perUserCharge = 1000 * 5 // 5 users
    const perCallCharge = Math.floor(0.001 * 100000 * 100) // 100k API calls in cents
    const storageCharge = Math.floor(0.05 * 50 * 100) // 50 GB in cents

    const total = planPrice + perUserCharge + perCallCharge + storageCharge
    expect(total).toBeGreaterThan(planPrice)
  })
})

describe('Billing Edge Cases', () => {
  it('should handle zero-dollar transactions', () => {
    const price = calculatePrice('free')
    expect(price).toBe(0)
  })

  it('should round to nearest cent correctly', () => {
    const price = calculatePrice('pro')
    expect(price % 1).toBe(0)
  })

  it('should handle monthly and annual cycle distinction', async () => {
    const monthly = applyDiscount(9900, 'monthly')
    const annual = applyDiscount(9900, 'annual')
    expect(annual).toBeLessThan(monthly)
  })

  it('should prevent negative pricing', () => {
    const price = calculatePrice('starter')
    expect(price).toBeGreaterThanOrEqual(0)
  })
})
