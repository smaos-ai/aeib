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

let slackToken: string = '';
let sentMessages: SentMessage[] = [];

export function initSlack(token: string): void {
  slackToken = token;
}

export async function sendAlert(alert: AlertMessage): Promise<void> {
  const message: SentMessage = {
    ...alert,
    timestamp: Date.now()
  };

  sentMessages.push(message);
}

export function getSentMessages(): SentMessage[] {
  return [...sentMessages];
}

export function clearMessages(): void {
  sentMessages = [];
}

export function getMessagesByChannel(channel: string): SentMessage[] {
  return sentMessages.filter(m => m.channel === channel);
}

export function getMessagesBySeverity(
  severity: 'critical' | 'warning' | 'info'
): SentMessage[] {
  return sentMessages.filter(m => m.severity === severity);
}
