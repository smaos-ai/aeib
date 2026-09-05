import * as crypto from 'crypto';

interface QueryResult {
  query: string;
  duration: number;
  isSlow: boolean;
  timestamp: number;
}

interface ParsedQuery {
  type: string;
  tables: string[];
  whereConditions?: string[];
}

interface QueryStats {
  query: string;
  executionCount: number;
  avgDuration: number;
  minDuration: number;
  maxDuration: number;
  slowPercentage: number;
  lastExecution: number;
}

interface Anomaly {
  query: string;
  type: string;
  severity: string;
  baseline: number;
  observed: number;
}

export class QueryAnalyzer {
  private slowQueryLogs: string[] = [];
  private queryStats: Map<string, { count: number; total: number; min: number; max: number; slow: number; }> = new Map();
  private queryExecutions: Map<string, number[]> = new Map();
  private readonly SLOW_QUERY_THRESHOLD = 100; // ms
  private readonly MAX_LOG_SIZE = 1000;

  analyzeQuery(query: string, duration: number): QueryResult {
    const timestamp = Date.now();
    const isSlow = duration > this.SLOW_QUERY_THRESHOLD;

    const result: QueryResult = {
      query,
      duration,
      isSlow,
      timestamp
    };

    if (isSlow) {
      this.logSlowQuery(query, duration, timestamp);
    }

    this.updateStats(query, duration);
    this.recordExecution(query, duration);

    return result;
  }

  parseQuery(query: string): ParsedQuery {
    const upperQuery = query.toUpperCase();
    let type = 'UNKNOWN';
    const tables: string[] = [];

    if (upperQuery.startsWith('SELECT')) {
      type = 'SELECT';
    } else if (upperQuery.startsWith('INSERT')) {
      type = 'INSERT';
    } else if (upperQuery.startsWith('UPDATE')) {
      type = 'UPDATE';
    } else if (upperQuery.startsWith('DELETE')) {
      type = 'DELETE';
    }

    // Extract tables
    const fromMatch = query.match(/FROM\s+(\w+)/i);
    if (fromMatch) tables.push(fromMatch[1]);

    const updateMatch = query.match(/UPDATE\s+(\w+)/i);
    if (updateMatch && !tables.includes(updateMatch[1])) {
      tables.push(updateMatch[1]);
    }

    const joinMatches = query.matchAll(/JOIN\s+(\w+)/gi);
    for (const match of joinMatches) {
      if (!tables.includes(match[1])) {
        tables.push(match[1]);
      }
    }

    const intoMatch = query.match(/INTO\s+(\w+)/i);
    if (intoMatch && !tables.includes(intoMatch[1])) {
      tables.push(intoMatch[1]);
    }

    // Extract WHERE conditions
    const whereConditions: string[] = [];
    const whereMatch = query.match(/WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|$)/i);
    if (whereMatch) {
      const conditions = whereMatch[1].split(/\s+AND\s+/i);
      whereConditions.push(...conditions);
    }

    return { type, tables, whereConditions: whereConditions.length > 0 ? whereConditions : undefined };
  }

  suggestIndexes(query: string): string[] {
    const suggestions: string[] = [];
    const parsed = this.parseQuery(query);

    // Suggest index for WHERE columns
    if (parsed.whereConditions) {
      for (const condition of parsed.whereConditions) {
        const colMatch = condition.match(/(\w+)\s*[=><]/);
        if (colMatch && colMatch[1] !== 'id') {
          suggestions.push(`Index on ${colMatch[1]}`);
        }
      }
    }

    // Suggest index for JOIN columns
    const joinMatches = query.matchAll(/ON\s+(\w+\.)?(\w+)\s*=\s*(\w+\.)?(\w+)/gi);
    for (const match of joinMatches) {
      if (match[2] !== 'id') suggestions.push(`Index on ${match[2]}`);
      if (match[4] !== 'id') suggestions.push(`Index on ${match[4]}`);
    }

    // Suggest index for ORDER BY
    const orderMatch = query.match(/ORDER\s+BY\s+(\w+)/i);
    if (orderMatch && orderMatch[1] !== 'id') {
      suggestions.push(`Index on ${orderMatch[1]}`);
    }

    return [...new Set(suggestions)].slice(0, 3);
  }

  getSlowQueryLogs(): string[] {
    return [...this.slowQueryLogs];
  }

  clearSlowQueryLogs(): void {
    this.slowQueryLogs = [];
  }

  getQueryStats(query: string): QueryStats | undefined {
    const stats = this.queryStats.get(query);
    if (!stats) return undefined;

    return {
      query,
      executionCount: stats.count,
      avgDuration: Math.round(stats.total / stats.count),
      minDuration: stats.min,
      maxDuration: stats.max,
      slowPercentage: Math.round((stats.slow / stats.count) * 100),
      lastExecution: Date.now()
    };
  }

  getTopSlowQueries(limit: number): QueryResult[] {
    const results: QueryResult[] = [];
    for (const log of this.slowQueryLogs) {
      // Log format: [timestamp] Slow Query (Xms): query
      const match = log.match(/Slow Query \((\d+)ms\):/);
      if (match) {
        results.push({
          query: log,
          duration: parseInt(match[1]),
          isSlow: true,
          timestamp: Date.now()
        });
      }
    }
    return results.sort((a, b) => b.duration - a.duration).slice(0, limit);
  }

  getQueryFingerprint(query: string): string {
    // Normalize query by replacing literals with ?
    const normalized = query
      .replace(/'\d+'/g, '?')
      .replace(/'\w+'/g, '?')
      .replace(/\d+/g, '?')
      .toLowerCase();
    return crypto.createHash('md5').update(normalized).digest('hex');
  }

  assessComplexity(query: string): number {
    let complexity = 0;

    if (query.toUpperCase().includes('JOIN')) {
      const joinCount = (query.match(/JOIN/gi) || []).length;
      complexity += 3 + joinCount * 2;
    }

    // Check for subqueries (nested SELECT)
    const selectCount = (query.match(/SELECT/gi) || []).length;
    if (selectCount > 1) {
      complexity += 6; // Higher than 5 for subqueries
    }

    if (query.toUpperCase().includes('GROUP BY')) {
      complexity += 2;
    }

    if (query.toUpperCase().includes('HAVING')) {
      complexity += 2;
    }

    if (query.toUpperCase().includes('UNION')) {
      complexity += 3;
    }

    if (query.toUpperCase().includes('DISTINCT')) {
      complexity += 1;
    }

    return Math.max(1, complexity);
  }

  detectAnomalies(): Anomaly[] {
    const anomalies: Anomaly[] = [];

    for (const [query, durations] of this.queryExecutions) {
      if (durations.length < 5) continue;

      const avg = durations.reduce((a, b) => a + b) / durations.length;
      const recent = durations[durations.length - 1];

      if (recent > avg * 5) {
        anomalies.push({
          query,
          type: 'Latency Spike',
          severity: recent > avg * 10 ? 'critical' : 'warning',
          baseline: Math.round(avg),
          observed: recent
        });
      }
    }

    return anomalies;
  }

  private logSlowQuery(query: string, duration: number, timestamp: number): void {
    const date = new Date(timestamp).toISOString();
    const logEntry = `[${date}] Slow Query (${duration}ms): ${query}`;
    this.slowQueryLogs.push(logEntry);

    if (this.slowQueryLogs.length > this.MAX_LOG_SIZE) {
      this.slowQueryLogs.shift();
    }
  }

  private updateStats(query: string, duration: number): void {
    const stats = this.queryStats.get(query) ?? {
      count: 0,
      total: 0,
      min: Number.MAX_SAFE_INTEGER,
      max: 0,
      slow: 0
    };

    stats.count++;
    stats.total += duration;
    stats.min = Math.min(stats.min, duration);
    stats.max = Math.max(stats.max, duration);
    if (duration > this.SLOW_QUERY_THRESHOLD) {
      stats.slow++;
    }

    this.queryStats.set(query, stats);
  }

  private recordExecution(query: string, duration: number): void {
    if (!this.queryExecutions.has(query)) {
      this.queryExecutions.set(query, []);
    }
    this.queryExecutions.get(query)!.push(duration);

    // Keep only last 100 executions per query
    const durations = this.queryExecutions.get(query)!;
    if (durations.length > 100) {
      durations.shift();
    }
  }
}
