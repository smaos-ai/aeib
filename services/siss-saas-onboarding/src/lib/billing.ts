import * as crypto from 'crypto'

// Mock Stripe integration (replace with real Stripe SDK in production)
const stripe = {
  customers: new Map<string, any>(),
  subscriptions: new Map<string, any>(),
  paymentIntents: new Map<string, any>()
}

const PLAN_PRICES: Record<string, number> = {
  starter: 9900, // $99 in cents
  pro: 29900, // $299 in cents
  enterprise: 99900, // $999 in cents
  free: 0
}

const QUOTAS: Record<string, Record<string, number>> = {
  starter: {
    apiCalls: 1000000,
    storageGB: 100,
    computeMinutes: 1000
  },
  pro: {
    apiCalls: 10000000,
    storageGB: 1000,
    computeMinutes: 10000
  },
  enterprise: {
    apiCalls: Infinity,
    storageGB: Infinity,
    computeMinutes: Infinity
  }
}

export function calculatePrice(plan: string): number {
  return PLAN_PRICES[plan] || 0
}

export function applyDiscount(basePrice: number, billingInterval: string = 'monthly'): number {
  if (billingInterval === 'annual') {
    return Math.round(basePrice * 0.9) // 10% discount
  }
  return basePrice
}

export async function createStripeCustomer(
  tenantId: string,
  email: string,
  companyName: string,
  cardToken: string = 'tok_visa'
): Promise<string> {
  if (!email || !companyName) {
    throw new Error('Email and company name required')
  }

  // Mock Stripe validation
  if (cardToken && cardToken === 'invalid_token') {
    throw new Error('Invalid Stripe token')
  }

  const customerId = 'cus_' + crypto.randomBytes(8).toString('hex')

  const customer = {
    id: customerId,
    tenantId,
    email,
    companyName,
    metadata: {
      tenantId
    },
    created: Date.now()
  }

  stripe.customers.set(customerId, customer)

  return customerId
}

export async function createStripeSubscription(
  customerId: string,
  priceId: string,
  interval: string = 'monthly'
): Promise<string> {
  if (!stripe.customers.has(customerId)) {
    throw new Error('Customer not found')
  }

  const subscriptionId = 'sub_' + crypto.randomBytes(8).toString('hex')

  const subscription = {
    id: subscriptionId,
    customerId,
    priceId,
    status: 'active',
    interval,
    created: Date.now(),
    currentPeriodEnd: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).getTime()
  }

  stripe.subscriptions.set(subscriptionId, subscription)

  return subscriptionId
}

export async function handlePaymentWebhook(event: any): Promise<any> {
  const { type, data } = event

  if (type === 'payment_intent.succeeded') {
    const paymentIntent = data.object
    return {
      status: 'success',
      paymentIntentId: paymentIntent.id,
      amount: paymentIntent.amount,
      customerId: paymentIntent.customer
    }
  }

  if (type === 'payment_intent.payment_failed') {
    return {
      status: 'failed',
      paymentIntentId: data.object.id,
      customerId: data.object.customer
    }
  }

  if (type === 'customer.subscription.updated') {
    const subscription = data.object
    return {
      status: 'updated',
      subscriptionId: subscription.id,
      customerId: subscription.customer,
      subscriptionStatus: subscription.status
    }
  }

  if (type === 'invoice.paid') {
    const invoice = data.object
    return {
      status: 'success',
      invoiceId: invoice.id,
      customerId: invoice.customer,
      amountPaid: invoice.amount_paid
    }
  }

  if (type === 'invoice.payment_failed') {
    const invoice = data.object
    return {
      status: 'failed',
      invoiceId: invoice.id,
      customerId: invoice.customer,
      amountDue: invoice.amount_due
    }
  }

  return { status: 'unknown' }
}

export function prorate(
  cycleStart: Date,
  cycleEnd: Date,
  changeDate: Date,
  oldPrice: number,
  newPrice: number
): number {
  const cycleDays = Math.floor(
    (cycleEnd.getTime() - cycleStart.getTime()) / (1000 * 60 * 60 * 24)
  )
  const daysRemaining = Math.floor(
    (cycleEnd.getTime() - changeDate.getTime()) / (1000 * 60 * 60 * 24)
  )

  if (newPrice > oldPrice) {
    // Upgrade: charge difference for remaining days
    const dailyRate = (newPrice - oldPrice) / cycleDays
    return Math.round(dailyRate * daysRemaining)
  } else {
    // Downgrade: credit difference
    const dailyRate = (oldPrice - newPrice) / cycleDays
    return Math.round((oldPrice - dailyRate * daysRemaining) / 30)
  }
}

export function getQuotaForPlan(plan: string): Record<string, number> {
  return QUOTAS[plan] || QUOTAS.starter
}

export function getStripeCustomerForTenant(tenantId: string): any {
  for (const [, customer] of stripe.customers) {
    if (customer.tenantId === tenantId) {
      return customer
    }
  }
  return null
}

export function getStripeSubscriptionForCustomer(customerId: string): any {
  for (const [, subscription] of stripe.subscriptions) {
    if (subscription.customerId === customerId) {
      return subscription
    }
  }
  return null
}

// Export for testing
export function getStripeData() {
  return stripe
}

export function clearStripeData() {
  stripe.customers.clear()
  stripe.subscriptions.clear()
  stripe.paymentIntents.clear()
}
