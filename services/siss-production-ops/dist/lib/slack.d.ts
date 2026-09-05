export interface AlertMessage {
    severity: 'critical' | 'warning' | 'info';
    title: string;
    channel: string;
    value: number;
    threshold: number;
    metric: string;
    context?: string;
    timestamp?: number;
}
export interface SentMessage extends AlertMessage {
    timestamp: number;
}
export declare function initSlack(token: string): void;
export declare function sendAlert(alert: AlertMessage): Promise<void>;
export declare function getSentMessages(): SentMessage[];
export declare function clearMessages(): void;
export declare function getMessagesByChannel(channel: string): SentMessage[];
export declare function getMessagesBySeverity(severity: 'critical' | 'warning' | 'info'): SentMessage[];
//# sourceMappingURL=slack.d.ts.map