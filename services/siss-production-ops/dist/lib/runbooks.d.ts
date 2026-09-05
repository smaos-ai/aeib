export interface Runbook {
    id: string;
    title: string;
    diagnosis: string;
    recovery_steps: string[];
    owner: string;
    escalation: string;
    affected_services: string[];
}
export declare function getRunbook(alertType: string): Runbook;
export declare function listRunbooks(): Array<{
    id: string;
    title: string;
}>;
export declare function addRunbook(runbook: Runbook): void;
//# sourceMappingURL=runbooks.d.ts.map