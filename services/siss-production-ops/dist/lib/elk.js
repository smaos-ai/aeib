let logStorage = [];
export function initELK() {
    logStorage = [];
}
export function ingestLog(log) {
    logStorage.push(log);
}
export function searchLogs(query) {
    if (!query || query.trim() === '') {
        return logStorage;
    }
    const queryLower = query.toLowerCase();
    return logStorage.filter(log => {
        return (log.user_id.toLowerCase().includes(queryLower) ||
            log.action.toLowerCase().includes(queryLower) ||
            log.resource.toLowerCase().includes(queryLower) ||
            log.level.toLowerCase().includes(queryLower) ||
            log.message.toLowerCase().includes(queryLower) ||
            log.timestamp.toLowerCase().includes(queryLower));
    });
}
export function getLogCount() {
    return logStorage.length;
}
export function clearLogs() {
    logStorage = [];
}
export function getLogs() {
    return [...logStorage];
}
//# sourceMappingURL=elk.js.map