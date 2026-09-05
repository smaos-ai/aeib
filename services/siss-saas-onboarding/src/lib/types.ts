export interface TenantRegistration {
  email: string
  companyName: string
  industry: string
}

export interface RegisteredTenant {
  tenantId: string
  email: string
  step: number
}

export interface BillingSetup {
  tenantId: string
  plan: 'starter' | 'pro' | 'enterprise'
  cardToken: string
  billingInterval?: 'monthly' | 'annual'
}

export interface BillingResult {
  stripeCustomerId: string
  subscriptionId: string
  monthlyPrice: number
  subscriptionStatus: string
  step: number
}

export interface TeamMember {
  tenantId: string
  email: string
  role: 'admin' | 'member'
}

export interface TeamMemberResult {
  userId: string
  role: 'admin' | 'member'
}

export interface DataSourceConfig {
  tenantId: string
  type: string
  host: string
  port: number
  database: string
  username: string
  password: string
}

export interface DataSourceResult {
  datasourceId: string
  encryptedCredentials: string
  status: string
  step: number
}

export interface ConfirmationResult {
  enabled: boolean
  step: number
  ledgerEntryId: string
  ledgerAction: string
  completedAt: string
}

export interface TenantContext {
  tenantId: string
  userId: string
  role: 'admin' | 'member' | 'viewer'
}

export interface BillingMetrics {
  planPrice: number
  perUserCharge: number
  perApiCallCharge: number
  perStorageCharge: number
  total: number
}

export interface UsageMetrics {
  apiCalls: number
  storageGB: number
  computeMinutes: number
  lastUpdated: string
  apiCallsByEndpoint?: Record<string, number>
  apiCallsByMethod?: Record<string, number>
}

export interface RLSPolicy {
  rls_policy: string
  enforce: boolean
  tenantId: string
  operation: string
}

export interface TenantContextValidation {
  valid: boolean
  error?: string
}
