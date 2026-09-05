export interface StructuredLog {
    timestamp: string;
    user_id: string;
    action: string;
    resource: string;
    level: string;
    message: string;
}
export declare function initELK(): void;
export declare function ingestLog(log: StructuredLog): void;
export declare function searchLogs(query: string): StructuredLog[];
export declare function getLogCount(): number;
export declare function clearLogs(): void;
export declare function getLogs(): StructuredLog[];
//# sourceMappingURL=elk.d.ts.map