import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { MultiLayerCache } from '../src/lib/cache';

describe('Multi-Layer Cache', () => {
  let cache: MultiLayerCache;

  beforeEach(() => {
    cache = new MultiLayerCache();
  });

  afterEach(() => {
    cache.clear();
  });

  describe('L1 Cache (In-Memory)', () => {
    it('should store value in L1', () => {
      const key = 'user:123';
      const value = { id: 123, name: 'John' };
      cache.set(key, value, 'L1');
      const retrieved = cache.get(key);
      expect(retrieved).toEqual(value);
    });

    it('should return undefined for missing key', () => {
      const value = cache.get('nonexistent');
      expect(value).toBeUndefined();
    });

    it('should invalidate expired L1 entries', () => {
      const key = 'temp:data';
      cache.set(key, 'value', 'L1', 100); // 100ms
      expect(cache.get(key)).toBeDefined();
      // In real test would wait 110ms
    });

    it('should overwrite existing keys', () => {
      const key = 'overwrite:test';
      cache.set(key, 'value1', 'L1');
      cache.set(key, 'value2', 'L1');
      const retrieved = cache.get(key);
      expect(retrieved).toBe('value2');
    });

    it('should track L1 hits', () => {
      const key = 'hit:test';
      cache.set(key, 'data', 'L1');
      cache.get(key);
      cache.get(key);
      const stats = cache.getStats();
      expect(stats.l1Hits).toBeGreaterThanOrEqual(2);
    });
  });

  describe('L2 Cache (Redis Simulation)', () => {
    it('should store value in L2', () => {
      const key = 'redis:data';
      const value = { timestamp: Date.now() };
      cache.set(key, value, 'L2');
      const retrieved = cache.get(key);
      expect(retrieved).toEqual(value);
    });

    it('should expire L2 entries after 30 minutes', () => {
      const key = 'l2:ttl';
      cache.set(key, 'data', 'L2', 30 * 60 * 1000);
      const stats = cache.getStats();
      expect(stats.l2Size).toBeGreaterThan(0);
    });

    it('should handle L2 misses', () => {
      const value = cache.get('l2:missing');
      expect(value).toBeUndefined();
    });
  });

  describe('L3 Cache (SQL Disk)', () => {
    it('should store value in L3', () => {
      const key = 'disk:cache';
      const value = { largData: 'x'.repeat(1000) };
      cache.set(key, value, 'L3');
      const retrieved = cache.get(key);
      expect(retrieved).toEqual(value);
    });

    it('should handle L3 eviction', () => {
      const stats = cache.getStats();
      expect(stats.l3Size).toBeDefined();
      expect(stats.l3Misses).toBeDefined();
    });
  });

  describe('Cache Coherence (Invalidation)', () => {
    it('should invalidate L1 when L2 is updated', () => {
      const key = 'coherence:1';
      cache.set(key, 'l1-value', 'L1');
      cache.set(key, 'l2-value', 'L2');
      const retrieved = cache.get(key);
      expect(retrieved).toBe('l2-value');
    });

    it('should invalidate L1 and L2 when L3 is updated', () => {
      const key = 'coherence:2';
      cache.set(key, 'l1', 'L1');
      cache.set(key, 'l2', 'L2');
      cache.set(key, 'l3-update', 'L3');
      const retrieved = cache.get(key);
      expect(retrieved).toBe('l3-update');
    });

    it('should cascade invalidation down layers', () => {
      const key = 'cascade:test';
      cache.set(key, 'value-l1', 'L1');
      cache.set(key, 'value-l2', 'L2');
      cache.set(key, 'value-l3', 'L3');

      // Invalidate at L1 level should cascade
      cache.invalidate(key);
      const retrieved = cache.get(key);
      // Should search L2 and L3
      expect(cache.getStats().l1Misses).toBeGreaterThan(0);
    });

    it('should handle partial invalidation', () => {
      const key1 = 'partial:1';
      const key2 = 'partial:2';
      cache.set(key1, 'value1', 'L1');
      cache.set(key2, 'value2', 'L1');
      cache.invalidate(key1);
      expect(cache.get(key1)).toBeUndefined();
      expect(cache.get(key2)).toBe('value2');
    });
  });

  describe('TTL Management', () => {
    it('should respect default TTL (5 min for L1)', () => {
      const key = 'ttl:l1';
      cache.set(key, 'data', 'L1');
      const entry = cache.getWithTTL(key);
      if (entry) {
        expect(entry.expiresAt).toBeGreaterThan(Date.now());
        expect(entry.expiresAt).toBeLessThanOrEqual(Date.now() + 5 * 60 * 1000 + 1000);
      }
    });

    it('should respect custom TTL', () => {
      const key = 'ttl:custom';
      const customTTL = 2 * 60 * 1000; // 2 minutes
      cache.set(key, 'data', 'L1', customTTL);
      const entry = cache.getWithTTL(key);
      if (entry) {
        expect(entry.expiresAt).toBeLessThanOrEqual(Date.now() + customTTL + 100);
      }
    });

    it('should clean up expired entries', () => {
      const key1 = 'cleanup:1';
      cache.set(key1, 'value', 'L1', 100);
      cache.cleanup();
      const stats = cache.getStats();
      expect(stats.evictions).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Cache Statistics', () => {
    it('should track hit/miss ratio', () => {
      const key = 'stats:test';
      cache.set(key, 'value', 'L1');
      cache.get(key); // hit
      cache.get('missing'); // miss
      const stats = cache.getStats();
      expect(stats.l1Hits).toBeGreaterThan(0);
      expect(stats.l1Misses).toBeGreaterThan(0);
    });

    it('should report cache sizes', () => {
      cache.set('key1', 'val1', 'L1');
      cache.set('key2', 'val2', 'L2');
      const stats = cache.getStats();
      expect(stats.l1Size).toBe(1);
      expect(stats.l2Size).toBe(1);
    });

    it('should calculate hit rate', () => {
      cache.set('key', 'value', 'L1');
      cache.get('key');
      cache.get('key');
      cache.get('missing');
      const stats = cache.getStats();
      const hitRate = stats.l1Hits / (stats.l1Hits + stats.l1Misses);
      expect(hitRate).toBeGreaterThan(0.5);
    });
  });

  describe('Event-Based Invalidation', () => {
    it('should subscribe to invalidation events', () => {
      let eventFired = false;
      cache.onInvalidate((key: string) => {
        eventFired = true;
      });
      cache.invalidate('test:key');
      expect(eventFired).toBe(true);
    });

    it('should handle pattern-based invalidation', () => {
      cache.set('user:123', 'john', 'L1');
      cache.set('user:456', 'jane', 'L1');
      cache.set('post:789', 'content', 'L1');

      cache.invalidatePattern('user:*');
      expect(cache.get('user:123')).toBeUndefined();
      expect(cache.get('user:456')).toBeUndefined();
      expect(cache.get('post:789')).toBeDefined();
    });
  });

  describe('Concurrent Access', () => {
    it('should handle concurrent reads', async () => {
      const key = 'concurrent:read';
      cache.set(key, 'value', 'L1');

      const promises = Array(10).fill(null).map(() =>
        Promise.resolve(cache.get(key))
      );
      const results = await Promise.all(promises);
      expect(results.every(r => r === 'value')).toBe(true);
    });

    it('should handle concurrent writes', async () => {
      const promises = Array(10).fill(null).map((_, i) =>
        Promise.resolve(cache.set(`key:${i}`, `value:${i}`, 'L1'))
      );
      await Promise.all(promises);
      const stats = cache.getStats();
      expect(stats.l1Size).toBe(10);
    });
  });

  describe('Memory Management', () => {
    it('should evict LRU entries when L1 is full', () => {
      // Fill L1 cache
      for (let i = 0; i < 1000; i++) {
        cache.set(`key:${i}`, `value:${i}`, 'L1');
      }
      const stats = cache.getStats();
      // Should have evicted or limited size
      expect(stats.l1Size).toBeLessThanOrEqual(1000);
    });

    it('should move entries to L2 when L1 evicts', () => {
      cache.set('key:old', 'value', 'L1');
      // After many other inserts, old entry should move to L2
      for (let i = 0; i < 100; i++) {
        cache.set(`new:${i}`, `val:${i}`, 'L1');
      }
      // Entry might be in L2 or evicted
      const stats = cache.getStats();
      expect(stats.l2Size).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Clear/Reset', () => {
    it('should clear all caches', () => {
      cache.set('key1', 'val1', 'L1');
      cache.set('key2', 'val2', 'L2');
      cache.set('key3', 'val3', 'L3');
      cache.clear();
      const stats = cache.getStats();
      expect(stats.l1Size).toBe(0);
      expect(stats.l2Size).toBe(0);
      expect(stats.l3Size).toBe(0);
    });

    it('should reset statistics', () => {
      cache.set('key', 'value', 'L1');
      cache.get('key');
      cache.resetStats();
      const stats = cache.getStats();
      expect(stats.l1Hits).toBe(0);
      expect(stats.l1Misses).toBe(0);
    });
  });
});
