export interface StructuredLog {
  timestamp: string;
  user_id: string;
  action: string;
  resource: string;
  level: string;
  message: string;
}

let logStorage: StructuredLog[] = [];

export function initELK(): void {
  logStorage = [];
}

export function ingestLog(log: StructuredLog): void {
  logStorage.push(log);
}

export function searchLogs(query: string): StructuredLog[] {
  if (!query || query.trim() === '') {
    return logStorage;
  }

  const queryLower = query.toLowerCase();

  return logStorage.filter(log => {
    return (
      log.user_id.toLowerCase().includes(queryLower) ||
      log.action.toLowerCase().includes(queryLower) ||
      log.resource.toLowerCase().includes(queryLower) ||
      log.level.toLowerCase().includes(queryLower) ||
      log.message.toLowerCase().includes(queryLower) ||
      log.timestamp.toLowerCase().includes(queryLower)
    );
  });
}

export function getLogCount(): number {
  return logStorage.length;
}

export function clearLogs(): void {
  logStorage = [];
}

export function getLogs(): StructuredLog[] {
  return [...logStorage];
}
