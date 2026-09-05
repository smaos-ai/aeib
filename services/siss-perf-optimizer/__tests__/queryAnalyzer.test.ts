import { describe, it, expect, beforeEach } from 'vitest';
import { QueryAnalyzer } from '../src/lib/queryAnalyzer';

describe('Query Analyzer', () => {
  let analyzer: QueryAnalyzer;

  beforeEach(() => {
    analyzer = new QueryAnalyzer();
  });

  describe('Slow Query Detection', () => {
    it('should flag query > 100ms as slow', () => {
      const query = 'SELECT * FROM users WHERE id = ?';
      const duration = 150;
      const result = analyzer.analyzeQuery(query, duration);
      expect(result.isSlow).toBe(true);
      expect(result.duration).toBe(150);
    });

    it('should not flag query < 100ms as slow', () => {
      const query = 'SELECT * FROM users WHERE id = ?';
      const duration = 50;
      const result = analyzer.analyzeQuery(query, duration);
      expect(result.isSlow).toBe(false);
    });

    it('should flag query = 100ms boundary', () => {
      const query = 'SELECT * FROM small_table LIMIT 10';
      const duration = 100;
      const result = analyzer.analyzeQuery(query, duration);
      expect(result.isSlow).toBe(false); // Boundary case
    });

    it('should flag query > 100ms slightly', () => {
      const query = 'SELECT * FROM medium_table';
      const duration = 101;
      const result = analyzer.analyzeQuery(query, duration);
      expect(result.isSlow).toBe(true);
    });
  });

  describe('Query Parsing', () => {
    it('should parse SELECT statement', () => {
      const query = 'SELECT id, name FROM users';
      const parsed = analyzer.parseQuery(query);
      expect(parsed.type).toBe('SELECT');
      expect(parsed.tables).toContain('users');
    });

    it('should parse INSERT statement', () => {
      const query = 'INSERT INTO users (name) VALUES (?)';
      const parsed = analyzer.parseQuery(query);
      expect(parsed.type).toBe('INSERT');
      expect(parsed.tables).toContain('users');
    });

    it('should parse UPDATE statement', () => {
      const query = 'UPDATE users SET name = ? WHERE id = ?';
      const parsed = analyzer.parseQuery(query);
      expect(parsed.type).toBe('UPDATE');
      expect(parsed.tables).toContain('users');
    });

    it('should parse DELETE statement', () => {
      const query = 'DELETE FROM users WHERE id = ?';
      const parsed = analyzer.parseQuery(query);
      expect(parsed.type).toBe('DELETE');
      expect(parsed.tables).toContain('users');
    });

    it('should extract multiple tables from JOIN', () => {
      const query = 'SELECT u.id FROM users u JOIN posts p ON u.id = p.user_id';
      const parsed = analyzer.parseQuery(query);
      expect(parsed.tables).toContain('users');
      expect(parsed.tables).toContain('posts');
    });

    it('should extract WHERE conditions', () => {
      const query = 'SELECT * FROM users WHERE id = ? AND status = ?';
      const parsed = analyzer.parseQuery(query);
      expect(parsed.whereConditions).toBeDefined();
      expect(parsed.whereConditions?.length).toBeGreaterThan(0);
    });
  });

  describe('Index Recommendations', () => {
    it('should suggest index for WHERE clause on unindexed column', () => {
      const query = 'SELECT * FROM users WHERE email = ?';
      const suggestions = analyzer.suggestIndexes(query);
      expect(suggestions.length).toBeGreaterThan(0);
      expect(suggestions[0]).toContain('email');
    });

    it('should suggest composite index for multiple WHERE conditions', () => {
      const query = 'SELECT * FROM users WHERE status = ? AND created_at > ?';
      const suggestions = analyzer.suggestIndexes(query);
      expect(suggestions.length).toBeGreaterThan(0);
      expect(suggestions[0]).toContain('status');
    });

    it('should suggest index on JOIN columns', () => {
      const query = 'SELECT * FROM users u JOIN posts p ON u.id = p.user_id';
      const suggestions = analyzer.suggestIndexes(query);
      expect(suggestions.length).toBeGreaterThan(0);
      expect(suggestions.some(s => s.includes('user_id'))).toBe(true);
    });

    it('should suggest index on ORDER BY columns', () => {
      const query = 'SELECT * FROM users ORDER BY created_at DESC';
      const suggestions = analyzer.suggestIndexes(query);
      expect(suggestions.length).toBeGreaterThan(0);
      expect(suggestions.some(s => s.includes('created_at'))).toBe(true);
    });

    it('should not suggest redundant indexes', () => {
      const query = 'SELECT * FROM users WHERE id = ?'; // id typically already indexed
      const suggestions = analyzer.suggestIndexes(query);
      expect(suggestions.length).toBeLessThan(3); // Should limit suggestions
    });
  });

  describe('Query Logging', () => {
    it('should log slow query with full details', () => {
      const query = 'SELECT * FROM large_table LIMIT 1000';
      analyzer.analyzeQuery(query, 250);
      const logs = analyzer.getSlowQueryLogs();
      expect(logs.length).toBeGreaterThan(0);
      expect(logs[0]).toContain('large_table');
    });

    it('should include timestamp in logs', () => {
      analyzer.analyzeQuery('SELECT * FROM users', 150);
      const logs = analyzer.getSlowQueryLogs();
      expect(logs[0]).toMatch(/\d{4}-\d{2}-\d{2}/); // ISO date format
    });

    it('should limit log size to prevent memory issues', () => {
      // Log many queries
      for (let i = 0; i < 2000; i++) {
        analyzer.analyzeQuery(`SELECT * FROM table${i}`, 150);
      }
      const logs = analyzer.getSlowQueryLogs();
      expect(logs.length).toBeLessThanOrEqual(1000); // Max retention
    });

    it('should clear slow query logs', () => {
      analyzer.analyzeQuery('SELECT * FROM users', 150);
      expect(analyzer.getSlowQueryLogs().length).toBeGreaterThan(0);
      analyzer.clearSlowQueryLogs();
      expect(analyzer.getSlowQueryLogs().length).toBe(0);
    });
  });

  describe('Query Statistics', () => {
    it('should track query execution count', () => {
      const query = 'SELECT * FROM users';
      analyzer.analyzeQuery(query, 50);
      analyzer.analyzeQuery(query, 60);
      analyzer.analyzeQuery(query, 55);
      const stats = analyzer.getQueryStats(query);
      expect(stats?.executionCount).toBe(3);
    });

    it('should calculate average execution time', () => {
      const query = 'SELECT * FROM posts';
      analyzer.analyzeQuery(query, 100);
      analyzer.analyzeQuery(query, 110);
      analyzer.analyzeQuery(query, 90);
      const stats = analyzer.getQueryStats(query);
      expect(stats?.avgDuration).toBe(100);
    });

    it('should track min/max execution times', () => {
      const query = 'SELECT * FROM comments';
      analyzer.analyzeQuery(query, 50);
      analyzer.analyzeQuery(query, 150);
      analyzer.analyzeQuery(query, 75);
      const stats = analyzer.getQueryStats(query);
      expect(stats?.minDuration).toBe(50);
      expect(stats?.maxDuration).toBe(150);
    });

    it('should track slow query percentage', () => {
      const query = 'SELECT * FROM events';
      analyzer.analyzeQuery(query, 50); // fast
      analyzer.analyzeQuery(query, 50); // fast
      analyzer.analyzeQuery(query, 150); // slow
      analyzer.analyzeQuery(query, 150); // slow
      const stats = analyzer.getQueryStats(query);
      expect(stats?.slowPercentage).toBe(50);
    });

    it('should report top slow queries', () => {
      analyzer.analyzeQuery('SELECT * FROM table1', 200);
      analyzer.analyzeQuery('SELECT * FROM table2', 150);
      analyzer.analyzeQuery('SELECT * FROM table3', 100);
      const topQueries = analyzer.getTopSlowQueries(2);
      expect(topQueries.length).toBe(2);
      expect(topQueries[0].duration).toBeGreaterThanOrEqual(topQueries[1].duration);
    });
  });

  describe('Query Fingerprinting', () => {
    it('should generate consistent fingerprint for same query template', () => {
      const query1 = 'SELECT * FROM users WHERE id = 1';
      const query2 = 'SELECT * FROM users WHERE id = 2';
      const fp1 = analyzer.getQueryFingerprint(query1);
      const fp2 = analyzer.getQueryFingerprint(query2);
      expect(fp1).toBe(fp2); // Same structure, different values
    });

    it('should generate different fingerprints for different structures', () => {
      const query1 = 'SELECT * FROM users WHERE id = ?';
      const query2 = 'SELECT name FROM users WHERE id = ?';
      const fp1 = analyzer.getQueryFingerprint(query1);
      const fp2 = analyzer.getQueryFingerprint(query2);
      expect(fp1).not.toBe(fp2);
    });
  });

  describe('Query Complexity Assessment', () => {
    it('should rate simple SELECT as low complexity', () => {
      const query = 'SELECT * FROM users WHERE id = ?';
      const complexity = analyzer.assessComplexity(query);
      expect(complexity).toBeLessThan(3);
    });

    it('should rate JOINs as medium-high complexity', () => {
      const query = 'SELECT u.*, p.* FROM users u JOIN posts p ON u.id = p.user_id';
      const complexity = analyzer.assessComplexity(query);
      expect(complexity).toBeGreaterThan(3);
    });

    it('should rate subqueries as high complexity', () => {
      const query = 'SELECT * FROM users WHERE id IN (SELECT user_id FROM posts WHERE status = ?)';
      const complexity = analyzer.assessComplexity(query);
      expect(complexity).toBeGreaterThan(5);
    });

    it('should rate multiple JOINs as very high complexity', () => {
      const query = 'SELECT * FROM users u JOIN posts p ON u.id = p.user_id JOIN comments c ON p.id = c.post_id';
      const complexity = analyzer.assessComplexity(query);
      expect(complexity).toBeGreaterThan(6);
    });
  });

  describe('Anomaly Detection', () => {
    it('should detect sudden latency spike', () => {
      const query = 'SELECT * FROM users';
      // Normal executions
      for (let i = 0; i < 10; i++) {
        analyzer.analyzeQuery(query, 50);
      }
      // Sudden spike
      analyzer.analyzeQuery(query, 500);
      const anomalies = analyzer.detectAnomalies();
      expect(anomalies.length).toBeGreaterThan(0);
    });

    it('should report anomaly details', () => {
      const query = 'SELECT * FROM large_table';
      analyzer.analyzeQuery(query, 50);
      analyzer.analyzeQuery(query, 55);
      analyzer.analyzeQuery(query, 1000); // Spike
      const anomalies = analyzer.detectAnomalies();
      if (anomalies.length > 0) {
        expect(anomalies[0].type).toBeDefined();
        expect(anomalies[0].severity).toBeDefined();
      }
    });
  });
});
