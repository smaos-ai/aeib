export interface IncidentRequest {
    title: string;
    severity: 'critical' | 'high' | 'medium' | 'low';
    service_id: string;
    description: string;
    assigned_to?: string;
}
export interface IncidentResponse extends IncidentRequest {
    incident_id: string;
    status: 'triggered' | 'acknowledged' | 'resolved';
    urgency: 'high' | 'low';
    created_at: string;
    resolved_at?: string;
    resolution_notes?: string;
}
export declare function initPagerDuty(token: string): void;
export declare function createIncident(request: IncidentRequest): Promise<IncidentResponse>;
export declare function resolveIncident(incidentId: string, resolution_notes: string): Promise<void>;
export declare function getIncidents(): IncidentResponse[];
export declare function clearIncidents(): void;
export declare function getIncidentById(incidentId: string): IncidentResponse | undefined;
//# sourceMappingURL=pagerduty.d.ts.map