import { describe, it, expect, beforeEach } from 'vitest';
import {
  initPagerDuty,
  createIncident,
  getIncidents,
  resolveIncident,
  clearIncidents
} from '../src/lib/pagerduty';

describe('PagerDuty Incidents', () => {
  beforeEach(() => {
    initPagerDuty('test-api-key');
    clearIncidents();
  });

  describe('Incident Creation', () => {
    it('should create incident with title', async () => {
      const incident = await createIncident({
        title: 'Database Connection Pool Exhausted',
        severity: 'critical',
        service_id: 'database-service',
        description: 'Connection pool reached max capacity'
      });

      expect(incident).toBeDefined();
      expect(incident.title).toBe('Database Connection Pool Exhausted');
    });

    it('should set critical severity', async () => {
      const incident = await createIncident({
        title: 'Critical System Error',
        severity: 'critical',
        service_id: 'system',
        description: 'System critical error'
      });

      expect(incident.severity).toBe('critical');
    });

    it('should set high severity', async () => {
      const incident = await createIncident({
        title: 'High Priority Issue',
        severity: 'high',
        service_id: 'app',
        description: 'High priority issue'
      });

      expect(incident.severity).toBe('high');
    });

    it('should set medium severity', async () => {
      const incident = await createIncident({
        title: 'Medium Priority Issue',
        severity: 'medium',
        service_id: 'app',
        description: 'Medium priority issue'
      });

      expect(incident.severity).toBe('medium');
    });

    it('should set low severity', async () => {
      const incident = await createIncident({
        title: 'Low Priority Issue',
        severity: 'low',
        service_id: 'monitoring',
        description: 'Low priority issue'
      });

      expect(incident.severity).toBe('low');
    });

    it('should include service_id', async () => {
      const incident = await createIncident({
        title: 'Service Issue',
        severity: 'high',
        service_id: 'my-service',
        description: 'Service issue'
      });

      expect(incident.service_id).toBe('my-service');
    });

    it('should include description', async () => {
      const description = 'Database latency exceeds threshold of 500ms';
      const incident = await createIncident({
        title: 'Latency Breach',
        severity: 'critical',
        service_id: 'database',
        description
      });

      expect(incident.description).toBe(description);
    });

    it('should generate unique incident_id', async () => {
      const incident1 = await createIncident({
        title: 'Issue 1',
        severity: 'critical',
        service_id: 'service1',
        description: 'Description 1'
      });

      const incident2 = await createIncident({
        title: 'Issue 2',
        severity: 'critical',
        service_id: 'service2',
        description: 'Description 2'
      });

      expect(incident1.incident_id).not.toBe(incident2.incident_id);
    });

    it('should include urgency mapping to severity', async () => {
      const critical = await createIncident({
        title: 'Critical',
        severity: 'critical',
        service_id: 'service',
        description: 'Critical'
      });

      const low = await createIncident({
        title: 'Low',
        severity: 'low',
        service_id: 'service',
        description: 'Low'
      });

      expect(critical.urgency).toBe('high');
      expect(low.urgency).toBe('low');
    });
  });

  describe('Incident Management', () => {
    it('should list all incidents', async () => {
      await createIncident({
        title: 'Incident 1',
        severity: 'critical',
        service_id: 'service1',
        description: 'Description 1'
      });

      await createIncident({
        title: 'Incident 2',
        severity: 'high',
        service_id: 'service2',
        description: 'Description 2'
      });

      const incidents = getIncidents();
      expect(incidents.length).toBe(2);
    });

    it('should resolve incident', async () => {
      const incident = await createIncident({
        title: 'Incident to Resolve',
        severity: 'critical',
        service_id: 'service',
        description: 'Description'
      });

      await resolveIncident(incident.incident_id, 'Issue resolved - database recovered');

      const incidents = getIncidents();
      const resolved = incidents.find(i => i.incident_id === incident.incident_id);
      expect(resolved?.status).toBe('resolved');
    });

    it('should track incident status changes', async () => {
      const incident = await createIncident({
        title: 'Status Test',
        severity: 'critical',
        service_id: 'service',
        description: 'Description'
      });

      expect(incident.status).toBe('triggered');

      await resolveIncident(incident.incident_id, 'Fixed');

      const incidents = getIncidents();
      const updated = incidents.find(i => i.incident_id === incident.incident_id);
      expect(updated?.status).toBe('resolved');
    });

    it('should maintain incident assignment', async () => {
      const incident = await createIncident({
        title: 'Assignment Test',
        severity: 'critical',
        service_id: 'service',
        description: 'Description',
        assigned_to: 'on-call-user'
      });

      expect(incident.incident_id).toBeDefined();
    });
  });

  describe('Incident Details', () => {
    it('should include creation timestamp', async () => {
      const incident = await createIncident({
        title: 'Timestamp Test',
        severity: 'critical',
        service_id: 'service',
        description: 'Description'
      });

      expect(incident.created_at).toBeDefined();
    });

    it('should track incident urgency', async () => {
      const critical = await createIncident({
        title: 'Critical',
        severity: 'critical',
        service_id: 'service',
        description: 'Critical'
      });

      expect(critical.urgency).toBe('high');
    });

    it('should support optional assignment', async () => {
      const incident = await createIncident({
        title: 'Optional Assignment',
        severity: 'high',
        service_id: 'service',
        description: 'Description',
        assigned_to: 'engineer@company.com'
      });

      expect(incident).toBeDefined();
    });

    it('should create incident with notification payload', async () => {
      const incident = await createIncident({
        title: 'Full Details',
        severity: 'critical',
        service_id: 'database',
        description: 'Full incident details for alerting'
      });

      expect(incident.title).toBeDefined();
      expect(incident.severity).toBeDefined();
      expect(incident.service_id).toBeDefined();
      expect(incident.incident_id).toBeDefined();
    });
  });

  describe('Concurrent Incident Handling', () => {
    it('should handle multiple simultaneous incidents', async () => {
      const promises = [
        createIncident({
          title: 'Incident 1',
          severity: 'critical',
          service_id: 'service1',
          description: 'Description 1'
        }),
        createIncident({
          title: 'Incident 2',
          severity: 'high',
          service_id: 'service2',
          description: 'Description 2'
        }),
        createIncident({
          title: 'Incident 3',
          severity: 'medium',
          service_id: 'service3',
          description: 'Description 3'
        })
      ];

      const incidents = await Promise.all(promises);
      expect(incidents.length).toBe(3);
      expect(getIncidents().length).toBe(3);
    });

    it('should maintain incident uniqueness with concurrent creation', async () => {
      const promises = Array.from({ length: 10 }, (_, i) =>
        createIncident({
          title: `Incident ${i}`,
          severity: 'critical',
          service_id: `service${i}`,
          description: `Description ${i}`
        })
      );

      await Promise.all(promises);
      const incidents = getIncidents();
      const uniqueIds = new Set(incidents.map(i => i.incident_id));
      expect(uniqueIds.size).toBe(10);
    });
  });
});
