import { GateType, SafetyGateResult } from './types';

function gate(type: GateType, pattern: RegExp, content: string, reason: string): SafetyGateResult {
  const matched = pattern.test(content);
  return {
    gate_type: type,
    passed: !matched,
    confidence: matched ? 0.95 : 1.0,
    reason: matched ? reason : 'clean',
  };
}

export function runXSSGate(content: string): SafetyGateResult {
  return gate(
    'XSSPrevention',
    /<script[\s\S]*?>|javascript\s*:|on\w+\s*=/i,
    content,
    'XSS pattern detected'
  );
}

export function runSQLInjectionGate(content: string): SafetyGateResult {
  return gate(
    'SQLInjectionPrevention',
    /(['";]|\b(DROP|DELETE|INSERT|UPDATE|UNION|SELECT)\b.*\b(FROM|INTO|TABLE|WHERE)\b)/i,
    content,
    'SQL injection pattern detected'
  );
}

export function runPromptInjectionGate(content: string): SafetyGateResult {
  return gate(
    'PromptInjectionPrevention',
    /ignore\s+(previous|above|prior)\s+instructions?|system\s*prompt|you\s+are\s+now/i,
    content,
    'Prompt injection pattern detected'
  );
}

export function runPIIRedactionGate(content: string): SafetyGateResult {
  return gate(
    'PIIRedaction',
    /\b\d{3}-\d{2}-\d{4}\b|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b/i,
    content,
    'PII pattern detected'
  );
}

export function runToxicityGate(content: string): SafetyGateResult {
  return gate(
    'ToxicityThreshold',
    /\b(kill|murder|bomb|terrorist|attack|rape|torture)\b/i,
    content,
    'Toxic content detected'
  );
}

export function runConfidentialityGate(content: string): SafetyGateResult {
  return gate(
    'ConfidentialityClassifier',
    /\b(confidential|top\s*secret|classified|internal\s*only|proprietary)\b/i,
    content,
    'Confidential marker detected'
  );
}

export function runAllGates(content: string): SafetyGateResult[] {
  return [
    runXSSGate(content),
    runSQLInjectionGate(content),
    runPromptInjectionGate(content),
    runPIIRedactionGate(content),
    runToxicityGate(content),
    runConfidentialityGate(content),
  ];
}
