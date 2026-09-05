interface CacheEntry {
  value: any;
  expiresAt: number;
  layer: string;
}

interface CacheStats {
  l1Size: number;
  l2Size: number;
  l3Size: number;
  l1Hits: number;
  l1Misses: number;
  l2Hits: number;
  l2Misses: number;
  l3Hits: number;
  l3Misses: number;
  evictions: number;
  lastCleanup: number;
}

type InvalidationCallback = (key: string) => void;

export class MultiLayerCache {
  private l1: Map<string, CacheEntry> = new Map();
  private l2: Map<string, CacheEntry> = new Map();
  private l3: Map<string, CacheEntry> = new Map();

  private stats: CacheStats = {
    l1Size: 0,
    l2Size: 0,
    l3Size: 0,
    l1Hits: 0,
    l1Misses: 0,
    l2Hits: 0,
    l2Misses: 0,
    l3Hits: 0,
    l3Misses: 0,
    evictions: 0,
    lastCleanup: Date.now()
  };

  private invalidationCallbacks: InvalidationCallback[] = [];
  private readonly L1_MAX_SIZE = 1000;
  private readonly L1_TTL = 5 * 60 * 1000; // 5 minutes
  private readonly L2_TTL = 30 * 60 * 1000; // 30 minutes
  private readonly L3_TTL = 60 * 60 * 1000; // 1 hour

  set(key: string, value: any, layer: string, ttl?: number): void {
    const now = Date.now();
    const expiresAt = now + (ttl ?? this.getTTLForLayer(layer));
    const entry: CacheEntry = { value, expiresAt, layer };

    if (layer === 'L1') {
      // Invalidate from higher layers when setting in L1
      this.l2.delete(key);
      this.l3.delete(key);
      this.l1.set(key, entry);
      this.stats.l1Size = this.l1.size;

      if (this.l1.size > this.L1_MAX_SIZE) {
        this.evictOldest();
      }
    } else if (layer === 'L2') {
      this.l1.delete(key);
      this.l3.delete(key);
      this.l2.set(key, entry);
      this.stats.l2Size = this.l2.size;
    } else if (layer === 'L3') {
      this.l1.delete(key);
      this.l2.delete(key);
      this.l3.set(key, entry);
      this.stats.l3Size = this.l3.size;
    }
  }

  get(key: string): any | undefined {
    const now = Date.now();

    // Check L1
    const l1Entry = this.l1.get(key);
    if (l1Entry) {
      if (now < l1Entry.expiresAt) {
        this.stats.l1Hits++;
        return l1Entry.value;
      } else {
        this.l1.delete(key);
      }
    }
    this.stats.l1Misses++;

    // Check L2
    const l2Entry = this.l2.get(key);
    if (l2Entry) {
      if (now < l2Entry.expiresAt) {
        this.stats.l2Hits++;
        // Promote to L1
        this.set(key, l2Entry.value, 'L1');
        return l2Entry.value;
      } else {
        this.l2.delete(key);
      }
    }
    this.stats.l2Misses++;

    // Check L3
    const l3Entry = this.l3.get(key);
    if (l3Entry) {
      if (now < l3Entry.expiresAt) {
        this.stats.l3Hits++;
        // Promote to L2
        this.set(key, l3Entry.value, 'L2');
        return l3Entry.value;
      } else {
        this.l3.delete(key);
      }
    }
    this.stats.l3Misses++;

    return undefined;
  }

  getWithTTL(key: string): { value: any; expiresAt: number } | undefined {
    const now = Date.now();

    const l1Entry = this.l1.get(key);
    if (l1Entry && now < l1Entry.expiresAt) {
      return { value: l1Entry.value, expiresAt: l1Entry.expiresAt };
    }

    const l2Entry = this.l2.get(key);
    if (l2Entry && now < l2Entry.expiresAt) {
      return { value: l2Entry.value, expiresAt: l2Entry.expiresAt };
    }

    const l3Entry = this.l3.get(key);
    if (l3Entry && now < l3Entry.expiresAt) {
      return { value: l3Entry.value, expiresAt: l3Entry.expiresAt };
    }

    return undefined;
  }

  invalidate(key: string): void {
    this.l1.delete(key);
    this.l2.delete(key);
    this.l3.delete(key);
    this.updateSizes();

    this.invalidationCallbacks.forEach(cb => cb(key));
  }

  invalidatePattern(pattern: string): void {
    const regex = new RegExp(`^${pattern.replace('*', '.*')}$`);

    for (const key of this.l1.keys()) {
      if (regex.test(key)) this.l1.delete(key);
    }
    for (const key of this.l2.keys()) {
      if (regex.test(key)) this.l2.delete(key);
    }
    for (const key of this.l3.keys()) {
      if (regex.test(key)) this.l3.delete(key);
    }

    this.updateSizes();
  }

  onInvalidate(callback: InvalidationCallback): void {
    this.invalidationCallbacks.push(callback);
  }

  getStats(): CacheStats {
    return { ...this.stats };
  }

  resetStats(): void {
    this.stats = {
      l1Size: this.l1.size,
      l2Size: this.l2.size,
      l3Size: this.l3.size,
      l1Hits: 0,
      l1Misses: 0,
      l2Hits: 0,
      l2Misses: 0,
      l3Hits: 0,
      l3Misses: 0,
      evictions: 0,
      lastCleanup: Date.now()
    };
  }

  cleanup(): void {
    const now = Date.now();
    let cleaned = 0;

    for (const [key, entry] of this.l1) {
      if (now >= entry.expiresAt) {
        this.l1.delete(key);
        cleaned++;
      }
    }

    for (const [key, entry] of this.l2) {
      if (now >= entry.expiresAt) {
        this.l2.delete(key);
        cleaned++;
      }
    }

    for (const [key, entry] of this.l3) {
      if (now >= entry.expiresAt) {
        this.l3.delete(key);
        cleaned++;
      }
    }

    if (cleaned > 0) {
      this.stats.evictions += cleaned;
    }

    this.updateSizes();
    this.stats.lastCleanup = Date.now();
  }

  clear(): void {
    this.l1.clear();
    this.l2.clear();
    this.l3.clear();
    this.updateSizes();
  }

  private evictOldest(): void {
    if (this.l1.size > this.L1_MAX_SIZE) {
      // Simple eviction: remove oldest entry
      const oldestKey = this.l1.keys().next().value;
      if (oldestKey) {
        const entry = this.l1.get(oldestKey)!;
        this.l1.delete(oldestKey);
        // Try to demote to L2
        if (this.l2.size < this.L1_MAX_SIZE * 2) {
          this.l2.set(oldestKey, entry);
        }
        this.stats.evictions++;
      }
    }
    this.updateSizes();
  }

  private getTTLForLayer(layer: string): number {
    switch (layer) {
      case 'L1':
        return this.L1_TTL;
      case 'L2':
        return this.L2_TTL;
      case 'L3':
        return this.L3_TTL;
      default:
        return this.L1_TTL;
    }
  }

  private updateSizes(): void {
    this.stats.l1Size = this.l1.size;
    this.stats.l2Size = this.l2.size;
    this.stats.l3Size = this.l3.size;
  }
}
