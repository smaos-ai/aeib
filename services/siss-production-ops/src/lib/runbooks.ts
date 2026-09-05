export interface Runbook {
  id: string;
  title: string;
  diagnosis: string;
  recovery_steps: string[];
  owner: string;
  escalation: string;
  affected_services: string[];
}

const runbooks: Record<string, Runbook> = {
  latency_breach: {
    id: 'latency_breach',
    title: 'Latency Breach Response',
    diagnosis: `Check database query performance. Review slow query logs and identify queries with high execution time.
Examine cache hit rates - low cache hit rates increase latency. Check for cache invalidation issues.
Monitor CPU and memory usage on application servers.
Review recent code deployments for performance regressions.
Check network latency between services.`,
    recovery_steps: [
      'Query database slow logs: SELECT query_time, query FROM slow_logs ORDER BY query_time DESC LIMIT 20',
      'Check cache hit rates from monitoring dashboard',
      'Review recent git commits and revert if necessary',
      'Scale additional instances if CPU/memory high',
      'Optimize database indexes for slow queries',
      'Enable query result caching for read-heavy operations'
    ],
    owner: 'Backend Team',
    escalation: 'If latency persists after 15 minutes, escalate to SRE team and database team',
    affected_services: ['api-gateway', 'database', 'cache-layer']
  },

  high_error_rate: {
    id: 'high_error_rate',
    title: 'High Error Rate Response',
    diagnosis: `Analyze error logs to identify error types and patterns.
Check for recent deployments or configuration changes.
Verify external service dependencies are healthy.
Review application logs for stack traces and error contexts.
Check disk space and system resources.`,
    recovery_steps: [
      'Aggregate errors by type from logs: SELECT error_type, COUNT(*) FROM error_logs GROUP BY error_type',
      'Check external service health endpoints',
      'Verify database connections and pool status',
      'Review recent deployment changelog',
      'Rollback latest deployment if errors started recently',
      'Scale application instances if under resource pressure'
    ],
    owner: 'SRE Team',
    escalation: 'If error rate exceeds 5% for more than 5 minutes, declare SEV-2 incident',
    affected_services: ['application', 'api', 'database', 'external-services']
  },

  compliance_drop: {
    id: 'compliance_drop',
    title: 'Compliance Score Drop Response',
    diagnosis: `Review compliance audit results to identify failed controls.
Check data governance policies for violations.
Verify encryption status of sensitive data.
Review access control logs for unauthorized access patterns.
Check audit trail completeness.`,
    recovery_steps: [
      'Pull latest compliance audit report and review failed controls',
      'Identify which data/systems are non-compliant',
      'Document non-compliance in incident ticket with evidence',
      'Verify encryption enabled on all data stores',
      'Review and tighten access control rules',
      'Run manual audit to verify corrective actions'
    ],
    owner: 'Compliance Team',
    escalation: 'If score drops below 80%, notify Legal and Regulatory Affairs teams',
    affected_services: ['data-governance', 'audit-system', 'access-control']
  }
};

export function getRunbook(alertType: string): Runbook {
  return runbooks[alertType] || {
    id: alertType,
    title: `Unknown Alert Type: ${alertType}`,
    diagnosis: 'No diagnostic information available for this alert type.',
    recovery_steps: ['Contact on-call engineer for assistance'],
    owner: 'Unknown',
    escalation: 'Escalate to duty manager',
    affected_services: []
  };
}

export function listRunbooks(): Array<{ id: string; title: string }> {
  return Object.values(runbooks).map(rb => ({
    id: rb.id,
    title: rb.title
  }));
}

export function addRunbook(runbook: Runbook): void {
  runbooks[runbook.id] = runbook;
}
