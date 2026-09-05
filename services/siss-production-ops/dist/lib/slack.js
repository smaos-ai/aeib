let slackToken = '';
let sentMessages = [];
export function initSlack(token) {
    slackToken = token;
}
export async function sendAlert(alert) {
    const message = {
        ...alert,
        timestamp: Date.now()
    };
    sentMessages.push(message);
}
export function getSentMessages() {
    return [...sentMessages];
}
export function clearMessages() {
    sentMessages = [];
}
export function getMessagesByChannel(channel) {
    return sentMessages.filter(m => m.channel === channel);
}
export function getMessagesBySeverity(severity) {
    return sentMessages.filter(m => m.severity === severity);
}
//# sourceMappingURL=slack.js.map