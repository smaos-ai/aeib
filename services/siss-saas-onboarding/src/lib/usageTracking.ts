import type { UsageMetrics } from './types'

// In-memory usage storage (replace with real DB in production)
const usageStore = new Map<string, UsageMetrics>()

// Track API call IDs to prevent duplicates
const apiCallIds = new Map<string, Set<string>>()

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

function initializeMetrics(tenantId: string): UsageMetrics {
  return {
    apiCalls: 0,
    storageGB: 0,
    computeMinutes: 0,
    lastUpdated: new Date().toISOString(),
    apiCallsByEndpoint: {},
    apiCallsByMethod: {}
  }
}

function getMetricsForTenant(tenantId: string): UsageMetrics {
  if (!usageStore.has(tenantId)) {
    usageStore.set(tenantId, initializeMetrics(tenantId))
  }
  return usageStore.get(tenantId)!
}

export async function trackAPICall(
  tenantId: string,
  method: string,
  endpoint: string,
  callId?: string
): Promise<void> {
  const metrics = getMetricsForTenant(tenantId)

  // Prevent duplicate counting
  if (callId) {
    if (!apiCallIds.has(tenantId)) {
      apiCallIds.set(tenantId, new Set())
    }
    const tenantCallIds = apiCallIds.get(tenantId)!
    if (tenantCallIds.has(callId)) {
      return // Already counted
    }
    tenantCallIds.add(callId)
  }

  metrics.apiCalls += 1
  metrics.lastUpdated = new Date().toISOString()

  // Track by endpoint
  if (!metrics.apiCallsByEndpoint) {
    metrics.apiCallsByEndpoint = {}
  }
  metrics.apiCallsByEndpoint[endpoint] = (metrics.apiCallsByEndpoint[endpoint] || 0) + 1

  // Track by method
  if (!metrics.apiCallsByMethod) {
    metrics.apiCallsByMethod = {}
  }
  metrics.apiCallsByMethod[method] = (metrics.apiCallsByMethod[method] || 0) + 1
}

export async function trackStorageUsage(tenantId: string, storageGB: number): Promise<void> {
  const metrics = getMetricsForTenant(tenantId)
  metrics.storageGB += storageGB
  metrics.lastUpdated = new Date().toISOString()
}

export async function trackComputeMinutes(tenantId: string, minutes: number): Promise<void> {
  const metrics = getMetricsForTenant(tenantId)
  metrics.computeMinutes += minutes
  metrics.lastUpdated = new Date().toISOString()
}

export async function getUsageMetrics(tenantId: string): Promise<UsageMetrics> {
  return getMetricsForTenant(tenantId)
}

export async function resetUsageMetrics(tenantId: string): Promise<void> {
  usageStore.set(tenantId, initializeMetrics(tenantId))
  apiCallIds.set(tenantId, new Set())
}

export interface QuotaValidation {
  apiCallQuotaMet: boolean
  storageQuotaMet: boolean
  computeQuotaMet: boolean
  usage?: UsageMetrics
  quotas?: Record<string, number>
}

export async function validateUsageQuotas(
  tenantId: string,
  plan: string
): Promise<QuotaValidation> {
  const metrics = getMetricsForTenant(tenantId)
  const quotas = QUOTAS[plan] || QUOTAS.starter

  const apiCallQuotaMet = metrics.apiCalls <= quotas.apiCalls
  const storageQuotaMet = metrics.storageGB <= quotas.storageGB
  const computeQuotaMet = metrics.computeMinutes <= quotas.computeMinutes

  return {
    apiCallQuotaMet,
    storageQuotaMet,
    computeQuotaMet,
    usage: metrics,
    quotas
  }
}

export function getQuotasForPlan(plan: string): Record<string, number> {
  return QUOTAS[plan] || QUOTAS.starter
}

export function calculateOverageCharges(
  metrics: UsageMetrics,
  plan: string
): Record<string, number> {
  const quotas = QUOTAS[plan] || QUOTAS.starter

  const apiCallOverage = Math.max(0, metrics.apiCalls - quotas.apiCalls) * 0.001
  const storageOverage = Math.max(0, metrics.storageGB - quotas.storageGB) * 0.05
  const computeOverage = Math.max(0, metrics.computeMinutes - quotas.computeMinutes) * 0.0001

  return {
    apiCallOverageCharge: apiCallOverage,
    storageOverageCharge: storageOverage,
    computeOverageCharge: computeOverage,
    totalOverageCharge: apiCallOverage + storageOverage + computeOverage
  }
}

export function getUsageMetricsSnapshot(): Record<string, UsageMetrics> {
  const snapshot: Record<string, UsageMetrics> = {}
  for (const [tenantId, metrics] of usageStore) {
    snapshot[tenantId] = { ...metrics }
  }
  return snapshot
}

export function clearUsageStore() {
  usageStore.clear()
  apiCallIds.clear()
}
