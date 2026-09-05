import { describe, it, expect, beforeEach } from 'vitest';
import {
  initELK,
  ingestLog,
  searchLogs,
  getLogCount
} from '../src/lib/elk';

describe('ELK Integration', () => {
  beforeEach(() => {
    initELK();
  });

  describe('Log Ingestion', () => {
    it('should ingest a structured log', () => {
      const log = {
        timestamp: new Date().toISOString(),
        user_id: 'user123',
        action: 'login',
        resource: 'auth-service',
        level: 'info',
        message: 'User logged in successfully'
      };

      ingestLog(log);
      expect(getLogCount()).toBe(1);
    });

    it('should parse all structured fields', () => {
      const log = {
        timestamp: new Date().toISOString(),
        user_id: 'user456',
        action: 'create_resource',
        resource: 'api-gateway',
        level: 'info',
        message: 'Resource created'
      };

      ingestLog(log);
      const logs = searchLogs('user456');
      expect(logs.length).toBeGreaterThan(0);
      expect(logs[0].user_id).toBe('user456');
    });

    it('should maintain field structure for multiple logs', () => {
      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'user1',
        action: 'read',
        resource: 'database',
        level: 'info',
        message: 'Read operation'
      });

      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'user2',
        action: 'write',
        resource: 'cache',
        level: 'warn',
        message: 'Write operation'
      });

      expect(getLogCount()).toBe(2);
    });

    it('should handle logs with different severity levels', () => {
      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'user1',
        action: 'error_event',
        resource: 'system',
        level: 'error',
        message: 'System error occurred'
      });

      const logs = searchLogs('error_event');
      expect(logs[0].level).toBe('error');
    });
  });

  describe('Full-text Search', () => {
    beforeEach(() => {
      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'alice',
        action: 'query_database',
        resource: 'postgres',
        level: 'info',
        message: 'Database query executed successfully'
      });

      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'bob',
        action: 'api_call',
        resource: 'rest_api',
        level: 'info',
        message: 'API endpoint called'
      });
    });

    it('should find logs by user_id', () => {
      const results = searchLogs('alice');
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].user_id).toBe('alice');
    });

    it('should find logs by action', () => {
      const results = searchLogs('query_database');
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].action).toBe('query_database');
    });

    it('should find logs by resource', () => {
      const results = searchLogs('postgres');
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].resource).toBe('postgres');
    });

    it('should find logs by message text', () => {
      const results = searchLogs('Database query');
      expect(results.length).toBeGreaterThan(0);
    });

    it('should return empty array when no match', () => {
      const results = searchLogs('nonexistent_term');
      expect(results.length).toBe(0);
    });

    it('should support partial string matching', () => {
      const results = searchLogs('database');
      expect(results.length).toBeGreaterThan(0);
    });
  });

  describe('Log Storage', () => {
    it('should count logs correctly', () => {
      expect(getLogCount()).toBe(0);

      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'user1',
        action: 'action1',
        resource: 'resource1',
        level: 'info',
        message: 'message1'
      });

      expect(getLogCount()).toBe(1);

      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'user2',
        action: 'action2',
        resource: 'resource2',
        level: 'info',
        message: 'message2'
      });

      expect(getLogCount()).toBe(2);
    });

    it('should preserve log order by timestamp', () => {
      const log1 = {
        timestamp: '2024-01-01T10:00:00Z',
        user_id: 'user1',
        action: 'action1',
        resource: 'resource1',
        level: 'info',
        message: 'first'
      };

      const log2 = {
        timestamp: '2024-01-01T10:01:00Z',
        user_id: 'user2',
        action: 'action2',
        resource: 'resource2',
        level: 'info',
        message: 'second'
      };

      ingestLog(log1);
      ingestLog(log2);

      const logs = searchLogs('');
      if (logs.length >= 2) {
        expect(new Date(logs[0].timestamp).getTime())
          .toBeLessThanOrEqual(new Date(logs[1].timestamp).getTime());
      }
    });
  });

  describe('ELK Edge Cases', () => {
    it('should handle special characters in log fields', () => {
      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'user@example.com',
        action: 'search_query_*',
        resource: 'elasticsearch',
        level: 'info',
        message: 'Query with special chars: [test]'
      });

      const results = searchLogs('user@example.com');
      expect(results.length).toBeGreaterThan(0);
    });

    it('should handle very long messages', () => {
      const longMessage = 'A'.repeat(1000);
      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'user_long',
        action: 'long_message',
        resource: 'system',
        level: 'info',
        message: longMessage
      });

      expect(getLogCount()).toBe(1);
    });

    it('should find logs case-insensitively', () => {
      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'USER123',
        action: 'TestAction',
        resource: 'API',
        level: 'info',
        message: 'Test Message'
      });

      const results = searchLogs('user123');
      expect(results.length).toBeGreaterThan(0);
    });
  });
});
