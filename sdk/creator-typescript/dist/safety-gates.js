"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.runXSSGate = runXSSGate;
exports.runSQLInjectionGate = runSQLInjectionGate;
exports.runPromptInjectionGate = runPromptInjectionGate;
exports.runPIIRedactionGate = runPIIRedactionGate;
exports.runToxicityGate = runToxicityGate;
exports.runConfidentialityGate = runConfidentialityGate;
exports.runAllGates = runAllGates;
function gate(type, pattern, content, reason) {
    const matched = pattern.test(content);
    return {
        gate_type: type,
        passed: !matched,
        confidence: matched ? 0.95 : 1.0,
        reason: matched ? reason : 'clean',
    };
}
function runXSSGate(content) {
    return gate('XSSPrevention', /<script[\s\S]*?>|javascript\s*:|on\w+\s*=/i, content, 'XSS pattern detected');
}
function runSQLInjectionGate(content) {
    return gate('SQLInjectionPrevention', /(['";]|\b(DROP|DELETE|INSERT|UPDATE|UNION|SELECT)\b.*\b(FROM|INTO|TABLE|WHERE)\b)/i, content, 'SQL injection pattern detected');
}
function runPromptInjectionGate(content) {
    return gate('PromptInjectionPrevention', /ignore\s+(previous|above|prior)\s+instructions?|system\s*prompt|you\s+are\s+now/i, content, 'Prompt injection pattern detected');
}
function runPIIRedactionGate(content) {
    return gate('PIIRedaction', /\b\d{3}-\d{2}-\d{4}\b|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b/i, content, 'PII pattern detected');
}
function runToxicityGate(content) {
    return gate('ToxicityThreshold', /\b(kill|murder|bomb|terrorist|attack|rape|torture)\b/i, content, 'Toxic content detected');
}
function runConfidentialityGate(content) {
    return gate('ConfidentialityClassifier', /\b(confidential|top\s*secret|classified|internal\s*only|proprietary)\b/i, content, 'Confidential marker detected');
}
function runAllGates(content) {
    return [
        runXSSGate(content),
        runSQLInjectionGate(content),
        runPromptInjectionGate(content),
        runPIIRedactionGate(content),
        runToxicityGate(content),
        runConfidentialityGate(content),
    ];
}
//# sourceMappingURL=safety-gates.js.map