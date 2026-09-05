import type { TenantContext, TenantContextValidation, RLSPolicy } from './types'

// In-memory data store with RLS enforcement
const dataStore = new Map<string, Map<string, any>>()

const VALID_ROLES = ['admin', 'member', 'viewer']

const MULTI_TENANT_TABLES = [
  'users',
  'teams',
  'documents',
  'subscriptions',
  'api_keys',
  'webhooks',
  'orders',
  'profiles',
  'sessions',
  'events',
  'secrets',
  'audit_logs',
  'invoices'
]

export function validateTenantContext(context: TenantContext): TenantContextValidation {
  if (!context.tenantId || context.tenantId.trim() === '') {
    return { valid: false, error: 'Missing tenant ID' }
  }

  if (!context.userId || context.userId.trim() === '') {
    return { valid: false, error: 'Missing user ID' }
  }

  if (!VALID_ROLES.includes(context.role)) {
    return { valid: false, error: 'Invalid role' }
  }

  return { valid: true }
}

export function enforceRowLevelSecurity(options: {
  table: string
  operation: string
  tenantId: string
}): RLSPolicy {
  const { table, operation, tenantId } = options

  const rls_policy = `tenant_id = '${tenantId}'`

  return {
    rls_policy,
    enforce: true,
    tenantId,
    operation
  }
}

export async function queryWithRLS(options: {
  table: string
  where: Record<string, any>
  tenantId: string
}): Promise<any[]> {
  const { table, where, tenantId } = options

  // Initialize table if not exists
  if (!dataStore.has(table)) {
    dataStore.set(table, new Map())
  }

  const tableData = dataStore.get(table)!

  // Filter by tenant_id
  const results: any[] = []

  for (const [, record] of tableData) {
    // Skip if tenant_id doesn't match
    if (record.tenant_id !== tenantId) {
      continue
    }

    // Check where conditions
    let matches = true
    for (const [key, value] of Object.entries(where)) {
      if (record[key] !== value) {
        matches = false
        break
      }
    }

    if (matches) {
      results.push(record)
    }
  }

  return results
}

export async function insertWithRLS(options: {
  table: string
  data: Record<string, any>
  tenantId: string
}): Promise<any> {
  const { table, data, tenantId } = options

  // Validate tenant context
  if (!tenantId) {
    throw new Error('Missing tenant context')
  }

  // Initialize table if not exists
  if (!dataStore.has(table)) {
    dataStore.set(table, new Map())
  }

  const tableData = dataStore.get(table)!

  // Force tenant_id to match context (prevent spoofing)
  const record = {
    ...data,
    tenant_id: tenantId,
    created_at: new Date().toISOString()
  }

  // Generate ID if not provided
  if (!record.id) {
    record.id = `${table}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  tableData.set(record.id, record)

  return record
}

export async function updateWithRLS(options: {
  table: string
  id: string
  data: Record<string, any>
  tenantId: string
}): Promise<any> {
  const { table, id, data, tenantId } = options

  if (!dataStore.has(table)) {
    throw new Error(`Table ${table} not found`)
  }

  const tableData = dataStore.get(table)!
  const record = tableData.get(id)

  if (!record) {
    throw new Error(`Record ${id} not found`)
  }

  // RLS check: verify tenant_id matches
  if (record.tenant_id !== tenantId) {
    throw new Error('Access denied: tenant mismatch')
  }

  const updated = {
    ...record,
    ...data,
    tenant_id: tenantId, // Force tenant_id
    updated_at: new Date().toISOString()
  }

  tableData.set(id, updated)
  return updated
}

export async function deleteWithRLS(options: {
  table: string
  id: string
  tenantId: string
}): Promise<boolean> {
  const { table, id, tenantId } = options

  if (!dataStore.has(table)) {
    throw new Error(`Table ${table} not found`)
  }

  const tableData = dataStore.get(table)!
  const record = tableData.get(id)

  if (!record) {
    throw new Error(`Record ${id} not found`)
  }

  // RLS check: verify tenant_id matches
  if (record.tenant_id !== tenantId) {
    throw new Error('Access denied: tenant mismatch')
  }

  return tableData.delete(id)
}

export function getRLSPoliciesForTable(table: string): Record<string, any> {
  if (!MULTI_TENANT_TABLES.includes(table)) {
    return {
      enforced: false,
      reason: 'Table not multi-tenant'
    }
  }

  return {
    enforced: true,
    policies: {
      SELECT: `WHERE tenant_id = current_user.tenant_id`,
      INSERT: `WITH CHECK (tenant_id = current_user.tenant_id)`,
      UPDATE: `USING (tenant_id = current_user.tenant_id)`,
      DELETE: `USING (tenant_id = current_user.tenant_id)`
    }
  }
}

export function clearAllData() {
  dataStore.clear()
}

export function getDataStoreSnapshot() {
  const snapshot: Record<string, any[]> = {}
  for (const [table, data] of dataStore) {
    snapshot[table] = Array.from(data.values())
  }
  return snapshot
}
