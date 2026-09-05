import { SafetyGateResult } from '../types';
export declare function runXSSGate(content: string): SafetyGateResult;
export declare function runSQLInjectionGate(content: string): SafetyGateResult;
export declare function runPromptInjectionGate(content: string): SafetyGateResult;
export declare function runPIIRedactionGate(content: string): SafetyGateResult;
export declare function runToxicityGate(content: string): SafetyGateResult;
export declare function runConfidentialityGate(content: string): SafetyGateResult;
export declare function runAllGates(content: string): SafetyGateResult[];
//# sourceMappingURL=safety-gates.d.ts.map