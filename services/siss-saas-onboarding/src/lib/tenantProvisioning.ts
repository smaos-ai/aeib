import * as crypto from 'crypto'
import type {
  TenantRegistration,
  RegisteredTenant,
  BillingSetup,
  BillingResult,
  TeamMember,
  TeamMemberResult,
  DataSourceConfig,
  DataSourceResult,
  ConfirmationResult
} from './types'

// In-memory storage (replace with real DB in production)
const tenantRegistry = new Map<string, any>()
const userRegistry = new Map<string, any>()
const subscriptionRegistry = new Map<string, any>()
const dataSourceRegistry = new Map<string, any>()
const ledgerRegistry: any[] = []

const VALID_INDUSTRIES = [
  'Technology',
  'Finance',
  'Healthcare',
  'Retail',
  'Manufacturing',
  'Education',
  'Hospitality'
]

export function validateEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email)
}

export function validateTenantRegistration(input: TenantRegistration): void {
  if (!validateEmail(input.email)) {
    throw new Error('Invalid email format')
  }

  if (!input.companyName || input.companyName.trim() === '') {
    throw new Error('Company name required')
  }

  if (!VALID_INDUSTRIES.includes(input.industry)) {
    throw new Error('Invalid industry')
  }
}

export async function registerTenant(input: TenantRegistration): Promise<RegisteredTenant> {
  validateTenantRegistration(input)

  // Check for duplicate email
  for (const tenant of tenantRegistry.values()) {
    if (tenant.email === input.email) {
      throw new Error('Email already registered')
    }
  }

  const tenantId = 'tenant_' + crypto.randomUUID()

  const tenant = {
    tenantId,
    email: input.email,
    companyName: input.companyName,
    industry: input.industry,
    createdAt: new Date().toISOString(),
    step: 1,
    status: 'registered'
  }

  tenantRegistry.set(tenantId, tenant)

  return {
    tenantId,
    email: input.email,
    step: 1
  }
}

export async function setupBilling(input: BillingSetup): Promise<BillingResult> {
  const tenant = tenantRegistry.get(input.tenantId)
  if (!tenant) {
    throw new Error('Tenant not found')
  }

  const validPlans = ['starter', 'pro', 'enterprise']
  if (!validPlans.includes(input.plan)) {
    throw new Error('Invalid plan')
  }

  // Validate Stripe token (test: tok_visa is valid)
  if (!input.cardToken || input.cardToken === 'invalid-token') {
    throw new Error('Invalid Stripe token')
  }

  // Get pricing
  const { calculatePrice, applyDiscount } = await import('./billing')
  const basePrice = calculatePrice(input.plan)
  const monthlyPrice = applyDiscount(basePrice, input.billingInterval || 'monthly')

  // Create Stripe customer and subscription (mock)
  const stripeCustomerId = 'cus_' + crypto.randomBytes(8).toString('hex')
  const subscriptionId = 'sub_' + crypto.randomBytes(8).toString('hex')

  const subscription = {
    tenantId: input.tenantId,
    stripeCustomerId,
    subscriptionId,
    plan: input.plan,
    monthlyPrice,
    status: 'active',
    createdAt: new Date().toISOString(),
    cardToken: input.cardToken,
    billingInterval: input.billingInterval || 'monthly'
  }

  subscriptionRegistry.set(subscriptionId, subscription)
  tenant.step = 2
  tenant.subscriptionId = subscriptionId
  tenant.billingStatus = 'active'

  return {
    stripeCustomerId,
    subscriptionId,
    monthlyPrice,
    subscriptionStatus: 'active',
    step: 2
  }
}

export async function provisionTeam(input: TeamMember): Promise<TeamMemberResult> {
  const tenant = tenantRegistry.get(input.tenantId)
  if (!tenant) {
    throw new Error('Tenant not found')
  }

  if (tenant.step < 2) {
    throw new Error('Billing not completed')
  }

  const validRoles = ['admin', 'member']
  if (!validRoles.includes(input.role)) {
    throw new Error('Invalid role')
  }

  // Check team size limit (50 users)
  const teamSize = Array.from(userRegistry.values()).filter(
    (u: any) => u.tenantId === input.tenantId
  ).length

  if (teamSize >= 50) {
    throw new Error('Team size limit exceeded')
  }

  // Check for duplicate email in same tenant
  for (const user of userRegistry.values()) {
    if ((user as any).tenantId === input.tenantId && (user as any).email === input.email) {
      throw new Error('Email already in team')
    }
  }

  const userId = 'user_' + crypto.randomUUID()

  const user = {
    userId,
    tenantId: input.tenantId,
    email: input.email,
    role: input.role,
    createdAt: new Date().toISOString()
  }

  userRegistry.set(userId, user)

  if (tenant.step === 2) {
    tenant.step = 3
  }

  return {
    userId,
    role: input.role
  }
}

export async function connectDataSource(input: DataSourceConfig): Promise<DataSourceResult> {
  const tenant = tenantRegistry.get(input.tenantId)
  if (!tenant) {
    throw new Error('Tenant not found')
  }

  if (tenant.step < 3) {
    throw new Error('Team not provisioned')
  }

  const validTypes = ['postgres', 'mysql', 'mongodb', 'dynamodb']
  if (!validTypes.includes(input.type)) {
    throw new Error('Invalid database type')
  }

  // Validate connection (mock validation)
  if (input.host === 'invalid-host' || input.port === 9999) {
    throw new Error('Failed to connect to database')
  }

  // Encrypt credentials
  const credentialString = JSON.stringify({
    host: input.host,
    port: input.port,
    database: input.database,
    username: input.username,
    password: input.password
  })

  const key = crypto.createHash('sha256').update('secret-key').digest()
  const iv = crypto.randomBytes(16)
  const cipher = crypto.createCipheriv('aes-256-cbc', key, iv)
  let encrypted = cipher.update(credentialString, 'utf8', 'hex')
  encrypted += cipher.final('hex')
  encrypted = iv.toString('hex') + ':' + encrypted

  const datasourceId = 'ds_' + crypto.randomUUID()

  const datasource = {
    datasourceId,
    tenantId: input.tenantId,
    type: input.type,
    encryptedCredentials: encrypted,
    status: 'connected',
    createdAt: new Date().toISOString()
  }

  dataSourceRegistry.set(datasourceId, datasource)
  tenant.step = 4
  tenant.datasourceId = datasourceId

  return {
    datasourceId,
    encryptedCredentials: encrypted,
    status: 'connected',
    step: 4
  }
}

export async function confirmOnboarding(tenantId: string): Promise<ConfirmationResult> {
  const tenant = tenantRegistry.get(tenantId)
  if (!tenant) {
    throw new Error('Tenant not found')
  }

  if (tenant.step < 4) {
    throw new Error('All steps must be completed')
  }

  tenant.enabled = true
  tenant.step = 5
  tenant.completedAt = new Date().toISOString()

  const ledgerEntryId = 'ledger_' + crypto.randomUUID()

  const ledgerEntry = {
    ledgerEntryId,
    tenantId,
    action: 'TENANT_ENABLED',
    timestamp: new Date().toISOString(),
    details: {
      email: tenant.email,
      companyName: tenant.companyName,
      plan: subscriptionRegistry.get(tenant.subscriptionId)?.plan || 'unknown'
    }
  }

  ledgerRegistry.push(ledgerEntry)

  return {
    enabled: true,
    step: 5,
    ledgerEntryId,
    ledgerAction: 'TENANT_ENABLED',
    completedAt: tenant.completedAt
  }
}

export async function rollbackTenant(tenantId: string, toStep: number = 0): Promise<void> {
  const tenant = tenantRegistry.get(tenantId)
  if (!tenant) {
    throw new Error('Tenant not found')
  }

  // Rollback step 2: Delete subscription
  if (toStep < 2 && tenant.subscriptionId) {
    subscriptionRegistry.delete(tenant.subscriptionId)
  }

  // Rollback step 3: Delete team members
  if (toStep < 3) {
    const teamMembers = Array.from(userRegistry.entries()).filter(
      ([, user]: [string, any]) => user.tenantId === tenantId
    )
    teamMembers.forEach(([userId]) => userRegistry.delete(userId))
  }

  // Rollback step 4: Delete data source
  if (toStep < 4 && tenant.datasourceId) {
    dataSourceRegistry.delete(tenant.datasourceId)
  }

  // Rollback step 1: Delete tenant entirely if toStep is 0
  if (toStep === 0) {
    tenantRegistry.delete(tenantId)
  } else {
    tenant.step = toStep
  }
}

// Export for testing
export function getTenantRegistry() {
  return tenantRegistry
}

export function getUserRegistry() {
  return userRegistry
}

export function getSubscriptionRegistry() {
  return subscriptionRegistry
}

export function getDataSourceRegistry() {
  return dataSourceRegistry
}

export function getLedgerRegistry() {
  return ledgerRegistry
}

export function clearAllRegistries() {
  tenantRegistry.clear()
  userRegistry.clear()
  subscriptionRegistry.clear()
  dataSourceRegistry.clear()
  ledgerRegistry.length = 0
}
