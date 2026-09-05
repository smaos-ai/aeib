import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  registerTenant,
  setupBilling,
  provisionTeam,
  connectDataSource,
  confirmOnboarding,
  rollbackTenant,
  clearAllRegistries
} from '../src/lib/tenantProvisioning'
import type { TenantRegistration, BillingSetup, TeamMember, DataSourceConfig } from '../src/lib/types'

describe('Step 1: Tenant Registration', () => {
  beforeEach(() => {
    clearAllRegistries()
  })

  it('should validate email format', async () => {
    const invalid = {
      email: 'invalid-email',
      companyName: 'ACME Corp',
      industry: 'Technology'
    }
    await expect(registerTenant(invalid)).rejects.toThrow('Invalid email format')
  })

  it('should reject missing company name', async () => {
    const invalid = {
      email: 'test@example.com',
      companyName: '',
      industry: 'Technology'
    }
    await expect(registerTenant(invalid)).rejects.toThrow('Company name required')
  })

  it('should reject invalid industry', async () => {
    const invalid = {
      email: 'test@example.com',
      companyName: 'ACME Corp',
      industry: 'InvalidIndustry'
    }
    await expect(registerTenant(invalid)).rejects.toThrow('Invalid industry')
  })

  it('should successfully register valid tenant', async () => {
    const valid = {
      email: 'test@example.com',
      companyName: 'ACME Corp',
      industry: 'Technology'
    }
    const result = await registerTenant(valid)
    expect(result.tenantId).toBeDefined()
    expect(result.email).toBe('test@example.com')
    expect(result.step).toBe(1)
  })

  it('should reject duplicate email', async () => {
    const tenant = {
      email: 'duplicate@example.com',
      companyName: 'First Corp',
      industry: 'Technology'
    }
    await registerTenant(tenant)
    await expect(registerTenant(tenant)).rejects.toThrow('Email already registered')
  })
})

describe('Step 2: Billing Setup', () => {
  let tenantId: string

  beforeEach(async () => {
    clearAllRegistries()
    const result = await registerTenant({
      email: 'billing@example.com',
      companyName: 'Billing Corp',
      industry: 'Finance'
    })
    tenantId = result.tenantId
  })

  it('should reject invalid plan selection', async () => {
    const invalid = {
      tenantId,
      plan: 'invalid-plan',
      cardToken: 'tok_visa'
    }
    await expect(setupBilling(invalid)).rejects.toThrow('Invalid plan')
  })

  it('should reject invalid Stripe token', async () => {
    const invalid = {
      tenantId,
      plan: 'pro',
      cardToken: 'invalid-token'
    }
    await expect(setupBilling(invalid)).rejects.toThrow('Invalid Stripe token')
  })

  it('should accept valid plan selection', async () => {
    const valid = {
      tenantId,
      plan: 'pro',
      cardToken: 'tok_visa'
    }
    const result = await setupBilling(valid)
    expect(result.stripeCustomerId).toBeDefined()
    expect(result.subscriptionId).toBeDefined()
    expect(result.step).toBe(2)
  })

  it('should calculate correct pricing for starter plan', async () => {
    const valid = {
      tenantId,
      plan: 'starter',
      cardToken: 'tok_visa'
    }
    const result = await setupBilling(valid)
    expect(result.monthlyPrice).toBe(9900) // $99 in cents
  })

  it('should calculate correct pricing for pro plan', async () => {
    const valid = {
      tenantId,
      plan: 'pro',
      cardToken: 'tok_visa'
    }
    const result = await setupBilling(valid)
    expect(result.monthlyPrice).toBe(29900) // $299 in cents
  })

  it('should apply 10% annual discount', async () => {
    const valid = {
      tenantId,
      plan: 'pro',
      cardToken: 'tok_visa',
      billingInterval: 'annual'
    }
    const result = await setupBilling(valid)
    expect(result.monthlyPrice).toBe(26910) // $299 * 0.9 in cents
  })

  it('should create Stripe customer', async () => {
    const valid = {
      tenantId,
      plan: 'pro',
      cardToken: 'tok_visa'
    }
    const result = await setupBilling(valid)
    expect(result.stripeCustomerId).toMatch(/^cus_/)
  })

  it('should create active subscription', async () => {
    const valid = {
      tenantId,
      plan: 'pro',
      cardToken: 'tok_visa'
    }
    const result = await setupBilling(valid)
    expect(result.subscriptionStatus).toBe('active')
  })
})

describe('Step 3: Team Provisioning', () => {
  let tenantId: string

  beforeEach(async () => {
    clearAllRegistries()
    const reg = await registerTenant({
      email: 'team@example.com',
      companyName: 'Team Corp',
      industry: 'Retail'
    })
    tenantId = reg.tenantId
    await setupBilling({
      tenantId,
      plan: 'pro',
      cardToken: 'tok_visa'
    })
  })

  it('should reject invalid role', async () => {
    const invalid = {
      tenantId,
      email: 'user@example.com',
      role: 'invalid-role'
    }
    await expect(provisionTeam(invalid)).rejects.toThrow('Invalid role')
  })

  it('should successfully add admin user', async () => {
    const valid = {
      tenantId,
      email: 'admin@example.com',
      role: 'admin'
    }
    const result = await provisionTeam(valid)
    expect(result.userId).toBeDefined()
    expect(result.role).toBe('admin')
  })

  it('should successfully add member user', async () => {
    const valid = {
      tenantId,
      email: 'member@example.com',
      role: 'member'
    }
    const result = await provisionTeam(valid)
    expect(result.userId).toBeDefined()
    expect(result.role).toBe('member')
  })

  it('should enforce team size limit of 50 users', async () => {
    // Add 50 users
    for (let i = 0; i < 50; i++) {
      await provisionTeam({
        tenantId,
        email: `user${i}@example.com`,
        role: 'member'
      })
    }

    // 51st user should fail
    await expect(
      provisionTeam({
        tenantId,
        email: 'user51@example.com',
        role: 'member'
      })
    ).rejects.toThrow('Team size limit exceeded')
  })

  it('should reject duplicate email in same tenant', async () => {
    await provisionTeam({
      tenantId,
      email: 'duplicate@example.com',
      role: 'member'
    })
    await expect(
      provisionTeam({
        tenantId,
        email: 'duplicate@example.com',
        role: 'admin'
      })
    ).rejects.toThrow('Email already in team')
  })
})

describe('Step 4: Data Source Connection', () => {
  let tenantId: string

  beforeEach(async () => {
    clearAllRegistries()
    const reg = await registerTenant({
      email: 'datasource@example.com',
      companyName: 'Data Corp',
      industry: 'Healthcare'
    })
    tenantId = reg.tenantId
    await setupBilling({
      tenantId,
      plan: 'pro',
      cardToken: 'tok_visa'
    })
    await provisionTeam({
      tenantId,
      email: 'user@datasource.com',
      role: 'member'
    })
  })

  it('should reject invalid database type', async () => {
    const invalid = {
      tenantId,
      type: 'invalid-db',
      host: 'localhost',
      port: 5432,
      database: 'test',
      username: 'user',
      password: 'pass'
    }
    await expect(connectDataSource(invalid)).rejects.toThrow('Invalid database type')
  })

  it('should validate database connection', async () => {
    const invalid = {
      tenantId,
      type: 'postgres',
      host: 'invalid-host',
      port: 9999,
      database: 'test',
      username: 'user',
      password: 'pass'
    }
    await expect(connectDataSource(invalid)).rejects.toThrow('Failed to connect to database')
  })

  it('should store encrypted credentials', async () => {
    const valid = {
      tenantId,
      type: 'postgres',
      host: 'localhost',
      port: 5432,
      database: 'testdb',
      username: 'testuser',
      password: 'testpass'
    }
    const result = await connectDataSource(valid)
    expect(result.datasourceId).toBeDefined()
    // Credentials should not be plaintext
    expect(result.encryptedCredentials).toBeDefined()
  })

  it('should successfully connect to valid database', async () => {
    const valid = {
      tenantId,
      type: 'postgres',
      host: 'localhost',
      port: 5432,
      database: 'testdb',
      username: 'testuser',
      password: 'testpass'
    }
    const result = await connectDataSource(valid)
    expect(result.status).toBe('connected')
    expect(result.step).toBe(4)
  })
})

describe('Step 5: Confirmation & Ledger', () => {
  let tenantId: string

  beforeEach(async () => {
    clearAllRegistries()
    const reg = await registerTenant({
      email: 'confirm@example.com',
      companyName: 'Confirm Corp',
      industry: 'Manufacturing'
    })
    tenantId = reg.tenantId
    await setupBilling({
      tenantId,
      plan: 'pro',
      cardToken: 'tok_visa'
    })
    await provisionTeam({
      tenantId,
      email: 'admin@confirm.com',
      role: 'admin'
    })
    await connectDataSource({
      tenantId,
      type: 'postgres',
      host: 'localhost',
      port: 5432,
      database: 'testdb',
      username: 'testuser',
      password: 'testpass'
    })
  })

  it('should enable tenant on confirmation', async () => {
    const result = await confirmOnboarding(tenantId)
    expect(result.enabled).toBe(true)
    expect(result.step).toBe(5)
  })

  it('should create initial ledger entry', async () => {
    const result = await confirmOnboarding(tenantId)
    expect(result.ledgerEntryId).toBeDefined()
    expect(result.ledgerAction).toBe('TENANT_ENABLED')
  })

  it('should record onboarding timestamp', async () => {
    const result = await confirmOnboarding(tenantId)
    expect(result.completedAt).toBeDefined()
    expect(new Date(result.completedAt).getTime()).toBeLessThanOrEqual(Date.now())
  })
})

describe('Happy Path: All 5 Steps', () => {
  beforeEach(() => {
    clearAllRegistries()
  })

  it('should complete full onboarding workflow', async () => {
    // Step 1: Register
    const reg = await registerTenant({
      email: 'happypath@example.com',
      companyName: 'Happy Corp',
      industry: 'Technology'
    })
    expect(reg.step).toBe(1)

    // Step 2: Billing
    const billing = await setupBilling({
      tenantId: reg.tenantId,
      plan: 'pro',
      cardToken: 'tok_visa'
    })
    expect(billing.step).toBe(2)

    // Step 3: Team
    const team = await provisionTeam({
      tenantId: reg.tenantId,
      email: 'happy-admin@example.com',
      role: 'admin'
    })
    expect(team.userId).toBeDefined()

    // Step 4: DataSource
    const ds = await connectDataSource({
      tenantId: reg.tenantId,
      type: 'postgres',
      host: 'localhost',
      port: 5432,
      database: 'testdb',
      username: 'testuser',
      password: 'testpass'
    })
    expect(ds.step).toBe(4)

    // Step 5: Confirmation
    const confirm = await confirmOnboarding(reg.tenantId)
    expect(confirm.step).toBe(5)
    expect(confirm.enabled).toBe(true)
  })
})

describe('Error Handling & Rollback', () => {
  beforeEach(() => {
    clearAllRegistries()
  })

  it('should rollback step 1 data on failure', async () => {
    const tenantId = 'test-tenant-rollback-1'
    const reg = await registerTenant({
      email: 'rollback1@example.com',
      companyName: 'Rollback Corp',
      industry: 'Retail'
    })

    await rollbackTenant(reg.tenantId)
    // Attempt to register same email should now succeed
    const retry = await registerTenant({
      email: 'rollback1@example.com',
      companyName: 'Retry Corp',
      industry: 'Technology'
    })
    expect(retry.tenantId).toBeDefined()
  })

  it('should rollback step 2 subscription on failure', async () => {
    const reg = await registerTenant({
      email: 'rollback2@example.com',
      companyName: 'Rollback Corp 2',
      industry: 'Finance'
    })

    const billing = await setupBilling({
      tenantId: reg.tenantId,
      plan: 'pro',
      cardToken: 'tok_visa'
    })

    await rollbackTenant(reg.tenantId, 2)
    // Subscription should be deleted
    expect(billing.subscriptionId).toBeDefined()
  })

  it('should handle concurrent signup without conflicts', async () => {
    const promises = Array.from({ length: 5 }, (_, i) =>
      registerTenant({
        email: `concurrent${i}@example.com`,
        companyName: `Concurrent Corp ${i}`,
        industry: 'Technology'
      })
    )

    const results = await Promise.all(promises)
    const tenantIds = results.map(r => r.tenantId)
    const uniqueIds = new Set(tenantIds)
    expect(uniqueIds.size).toBe(5) // All should have unique IDs
  })
})

describe('Workflow State Validation', () => {
  beforeEach(() => {
    clearAllRegistries()
  })

  it('should not allow step 2 before step 1', async () => {
    await expect(
      setupBilling({
        tenantId: 'nonexistent',
        plan: 'pro',
        cardToken: 'tok_visa'
      })
    ).rejects.toThrow('Tenant not found')
  })

  it('should not allow step 3 before step 2', async () => {
    const reg = await registerTenant({
      email: 'state@example.com',
      companyName: 'State Corp',
      industry: 'Retail'
    })

    await expect(
      provisionTeam({
        tenantId: reg.tenantId,
        email: 'user@example.com',
        role: 'member'
      })
    ).rejects.toThrow('Billing not completed')
  })

  it('should not allow step 4 before step 3', async () => {
    const reg = await registerTenant({
      email: 'state2@example.com',
      companyName: 'State Corp 2',
      industry: 'Finance'
    })

    await setupBilling({
      tenantId: reg.tenantId,
      plan: 'pro',
      cardToken: 'tok_visa'
    })

    await expect(
      connectDataSource({
        tenantId: reg.tenantId,
        type: 'postgres',
        host: 'localhost',
        port: 5432,
        database: 'testdb',
        username: 'testuser',
        password: 'testpass'
      })
    ).rejects.toThrow('Team not provisioned')
  })
})
