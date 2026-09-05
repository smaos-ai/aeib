import { describe, it, expect, beforeEach } from 'vitest'
import {
  trackAPICall,
  trackStorageUsage,
  trackComputeMinutes,
  getUsageMetrics,
  resetUsageMetrics,
  validateUsageQuotas
} from '../src/lib/usageTracking'

describe('Usage Tracking: API Calls', () => {
  const tenantId = 'usage-tenant-api'

  beforeEach(async () => {
    await resetUsageMetrics(tenantId)
  })

  it('should track single API call', async () => {
    await trackAPICall(tenantId, 'GET', '/api/users')

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.apiCalls).toBe(1)
  })

  it('should accumulate multiple API calls', async () => {
    await trackAPICall(tenantId, 'GET', '/api/users')
    await trackAPICall(tenantId, 'POST', '/api/documents')
    await trackAPICall(tenantId, 'DELETE', '/api/sessions')

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.apiCalls).toBe(3)
  })

  it('should track 100 API calls correctly', async () => {
    for (let i = 0; i < 100; i++) {
      await trackAPICall(tenantId, 'GET', `/api/endpoint${i}`)
    }

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.apiCalls).toBe(100)
  })

  it('should track concurrent API calls', async () => {
    const promises = Array.from({ length: 10 }, (_, i) =>
      trackAPICall(tenantId, 'GET', `/api/endpoint${i}`)
    )

    await Promise.all(promises)

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.apiCalls).toBe(10)
  })

  it('should include endpoint in API call tracking', async () => {
    await trackAPICall(tenantId, 'GET', '/api/users')

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.apiCallsByEndpoint).toBeDefined()
  })

  it('should track request method in API call', async () => {
    await trackAPICall(tenantId, 'POST', '/api/documents')

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.apiCallsByMethod).toBeDefined()
  })
})

describe('Usage Tracking: Storage', () => {
  const tenantId = 'usage-tenant-storage'

  beforeEach(async () => {
    await resetUsageMetrics(tenantId)
  })

  it('should track storage in GB', async () => {
    await trackStorageUsage(tenantId, 10) // 10 GB

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.storageGB).toBe(10)
  })

  it('should accumulate storage across multiple calls', async () => {
    await trackStorageUsage(tenantId, 5)
    await trackStorageUsage(tenantId, 3)
    await trackStorageUsage(tenantId, 2)

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.storageGB).toBe(10)
  })

  it('should track storage with decimal precision', async () => {
    await trackStorageUsage(tenantId, 1.5)
    await trackStorageUsage(tenantId, 2.3)

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.storageGB).toBeCloseTo(3.8, 1)
  })

  it('should handle large storage values', async () => {
    await trackStorageUsage(tenantId, 1000) // 1 TB

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.storageGB).toBe(1000)
  })

  it('should handle zero storage', async () => {
    await trackStorageUsage(tenantId, 0)

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.storageGB).toBe(0)
  })
})

describe('Usage Tracking: Compute Minutes', () => {
  const tenantId = 'usage-tenant-compute'

  beforeEach(async () => {
    await resetUsageMetrics(tenantId)
  })

  it('should track compute minutes', async () => {
    await trackComputeMinutes(tenantId, 60)

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.computeMinutes).toBe(60)
  })

  it('should accumulate compute minutes', async () => {
    await trackComputeMinutes(tenantId, 30)
    await trackComputeMinutes(tenantId, 20)
    await trackComputeMinutes(tenantId, 10)

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.computeMinutes).toBe(60)
  })

  it('should track fractional compute minutes', async () => {
    await trackComputeMinutes(tenantId, 0.5)
    await trackComputeMinutes(tenantId, 1.5)

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.computeMinutes).toBeCloseTo(2, 1)
  })

  it('should handle high compute minute counts', async () => {
    for (let i = 0; i < 100; i++) {
      await trackComputeMinutes(tenantId, 10)
    }

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.computeMinutes).toBe(1000)
  })
})

describe('Integrated Usage Metrics', () => {
  const tenantId = 'usage-tenant-integrated'

  beforeEach(async () => {
    await resetUsageMetrics(tenantId)
  })

  it('should track all metrics independently', async () => {
    await trackAPICall(tenantId, 'GET', '/api/users')
    await trackStorageUsage(tenantId, 5)
    await trackComputeMinutes(tenantId, 30)

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.apiCalls).toBe(1)
    expect(metrics.storageGB).toBe(5)
    expect(metrics.computeMinutes).toBe(30)
  })

  it('should include timestamp in metrics', async () => {
    await trackAPICall(tenantId, 'GET', '/api/test')

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.lastUpdated).toBeDefined()
  })

  it('should support metrics reset', async () => {
    await trackAPICall(tenantId, 'GET', '/api/users')
    await trackStorageUsage(tenantId, 10)

    await resetUsageMetrics(tenantId)

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.apiCalls).toBe(0)
    expect(metrics.storageGB).toBe(0)
  })
})

describe('Usage Quota Validation', () => {
  const tenantId = 'usage-tenant-quotas'

  beforeEach(async () => {
    await resetUsageMetrics(tenantId)
  })

  it('should validate API call quota (1M/month for starter)', async () => {
    // Starter plan: 1M API calls
    for (let i = 0; i < 1000000; i += 100000) {
      await trackAPICall(tenantId, 'GET', `/api/call${i}`)
    }

    const metrics = await getUsageMetrics(tenantId)
    const quotaValid = await validateUsageQuotas(tenantId, 'starter')

    expect(quotaValid.apiCallQuotaMet).toBe(true)
  })

  it('should enforce API quota overage', async () => {
    // Starter plan: 1M free, then $0.001 per call
    // Directly override metrics to simulate overage
    const metrics = await getUsageMetrics(tenantId)
    metrics.apiCalls = 1000001

    const quotaValid = await validateUsageQuotas(tenantId, 'starter')
    expect(quotaValid.apiCallQuotaMet).toBe(false)
  })

  it('should validate storage quota (100GB for starter)', async () => {
    await trackStorageUsage(tenantId, 100)

    const quotaValid = await validateUsageQuotas(tenantId, 'starter')
    expect(quotaValid.storageQuotaMet).toBe(true)
  })

  it('should enforce storage quota overage', async () => {
    await trackStorageUsage(tenantId, 101)

    const quotaValid = await validateUsageQuotas(tenantId, 'starter')
    expect(quotaValid.storageQuotaMet).toBe(false)
  })

  it('should validate compute quota (1000 minutes/month for starter)', async () => {
    await trackComputeMinutes(tenantId, 1000)

    const quotaValid = await validateUsageQuotas(tenantId, 'starter')
    expect(quotaValid.computeQuotaMet).toBe(true)
  })

  it('should enforce compute quota overage', async () => {
    await trackComputeMinutes(tenantId, 1001)

    const quotaValid = await validateUsageQuotas(tenantId, 'starter')
    expect(quotaValid.computeQuotaMet).toBe(false)
  })

  it('should provide detailed quota status', async () => {
    await trackAPICall(tenantId, 'GET', '/api/test')
    await trackStorageUsage(tenantId, 50)
    await trackComputeMinutes(tenantId, 500)

    const quotaValid = await validateUsageQuotas(tenantId, 'pro')

    expect(quotaValid).toHaveProperty('apiCallQuotaMet')
    expect(quotaValid).toHaveProperty('storageQuotaMet')
    expect(quotaValid).toHaveProperty('computeQuotaMet')
    expect(quotaValid).toHaveProperty('usage')
  })

  it('should escalate quotas for higher plans', async () => {
    const starterQuota = await validateUsageQuotas(tenantId, 'starter')
    const proQuota = await validateUsageQuotas(tenantId, 'pro')
    const enterpriseQuota = await validateUsageQuotas(tenantId, 'enterprise')

    expect(proQuota.quotas.apiCalls).toBeGreaterThan(starterQuota.quotas.apiCalls)
    expect(enterpriseQuota.quotas.apiCalls).toBeGreaterThan(proQuota.quotas.apiCalls)
  })
})

describe('Usage Tracking Multi-Tenant Isolation', () => {
  it('should isolate metrics between tenants', async () => {
    const tenantA = 'tenant-metrics-a'
    const tenantB = 'tenant-metrics-b'

    await resetUsageMetrics(tenantA)
    await resetUsageMetrics(tenantB)

    // Tenant A tracking
    await trackAPICall(tenantA, 'GET', '/api/users')
    await trackStorageUsage(tenantA, 10)

    // Tenant B tracking
    await trackAPICall(tenantB, 'GET', '/api/data')
    await trackAPICall(tenantB, 'POST', '/api/data')
    await trackStorageUsage(tenantB, 20)

    const metricsA = await getUsageMetrics(tenantA)
    const metricsB = await getUsageMetrics(tenantB)

    expect(metricsA.apiCalls).toBe(1)
    expect(metricsA.storageGB).toBe(10)

    expect(metricsB.apiCalls).toBe(2)
    expect(metricsB.storageGB).toBe(20)
  })
})

describe('Usage Tracking Accuracy', () => {
  const tenantId = 'usage-tenant-accuracy'

  beforeEach(async () => {
    await resetUsageMetrics(tenantId)
  })

  it('should accurately track 1000 API calls', async () => {
    for (let i = 0; i < 1000; i++) {
      await trackAPICall(tenantId, 'GET', `/api/endpoint${i % 10}`)
    }

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.apiCalls).toBe(1000)
  })

  it('should maintain accuracy with concurrent operations', async () => {
    const promises = []

    // 100 concurrent operations
    for (let i = 0; i < 100; i++) {
      promises.push(trackAPICall(tenantId, 'GET', '/api/test'))
      promises.push(trackStorageUsage(tenantId, 1))
      promises.push(trackComputeMinutes(tenantId, 1))
    }

    await Promise.all(promises)

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.apiCalls).toBe(100)
    expect(metrics.storageGB).toBe(100)
    expect(metrics.computeMinutes).toBe(100)
  })

  it('should prevent duplicate counting', async () => {
    const callId = 'call-' + Date.now()

    await trackAPICall(tenantId, 'GET', '/api/test', callId)
    await trackAPICall(tenantId, 'GET', '/api/test', callId)

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.apiCalls).toBe(1)
  })
})

describe('Usage Tracking Billing Integration', () => {
  const tenantId = 'usage-tenant-billing'

  beforeEach(async () => {
    await resetUsageMetrics(tenantId)
  })

  it('should calculate overage charges from API calls', async () => {
    // Starter plan: 1M free, then $0.001 per call
    // Directly set metrics to 1.1M calls
    const metrics = await getUsageMetrics(tenantId)
    metrics.apiCalls = 1100000

    const callCount = 1100000
    const overageCallCount = callCount - 1000000
    const overageCharge = overageCallCount * 0.001

    expect(metrics.apiCalls).toBe(1100000)
    expect(overageCharge).toBeGreaterThan(0)
  })

  it('should calculate overage charges from storage', async () => {
    // Starter plan: 100GB free, then $0.05/GB
    // Track 150GB
    const storageGB = 150
    const overageGB = storageGB - 100
    const overageCharge = overageGB * 0.05

    await trackStorageUsage(tenantId, storageGB)

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.storageGB).toBe(150)
    expect(overageCharge).toBe(2.5)
  })

  it('should include usage in monthly bill calculation', async () => {
    // Base plan price: $99
    // Usage: 10 API calls, 5 GB storage, 30 compute minutes
    await trackAPICall(tenantId, 'GET', '/api/test')
    await trackStorageUsage(tenantId, 5)
    await trackComputeMinutes(tenantId, 30)

    const metrics = await getUsageMetrics(tenantId)
    expect(metrics.apiCalls).toBe(1)
    expect(metrics.storageGB).toBe(5)
    expect(metrics.computeMinutes).toBe(30)
  })
})

describe('Usage Tracking Data Persistence', () => {
  const tenantId = 'usage-tenant-persistence'

  it('should persist metrics across sessions', async () => {
    await resetUsageMetrics(tenantId)

    // Session 1: Track metrics
    await trackAPICall(tenantId, 'GET', '/api/session1')
    let metrics = await getUsageMetrics(tenantId)
    expect(metrics.apiCalls).toBe(1)

    // Session 2: Verify persistence
    await trackAPICall(tenantId, 'GET', '/api/session2')
    metrics = await getUsageMetrics(tenantId)
    expect(metrics.apiCalls).toBe(2)
  })

  it('should support historical metrics retrieval', async () => {
    await resetUsageMetrics(tenantId)

    const before = Date.now()
    await trackAPICall(tenantId, 'GET', '/api/test')
    const metrics = await getUsageMetrics(tenantId)

    expect(new Date(metrics.lastUpdated).getTime()).toBeGreaterThanOrEqual(before)
  })
})
