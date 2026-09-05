import { v4 as uuidv4 } from 'uuid';
let apiKey = '';
let incidents = [];
export function initPagerDuty(token) {
    apiKey = token;
}
function severityToUrgency(severity) {
    if (severity === 'critical' || severity === 'high') {
        return 'high';
    }
    return 'low';
}
export async function createIncident(request) {
    const incident = {
        ...request,
        incident_id: `PD-${uuidv4()}`,
        status: 'triggered',
        urgency: severityToUrgency(request.severity),
        created_at: new Date().toISOString()
    };
    incidents.push(incident);
    return incident;
}
export async function resolveIncident(incidentId, resolution_notes) {
    const incident = incidents.find(i => i.incident_id === incidentId);
    if (incident) {
        incident.status = 'resolved';
        incident.resolved_at = new Date().toISOString();
        incident.resolution_notes = resolution_notes;
    }
}
export function getIncidents() {
    return [...incidents];
}
export function clearIncidents() {
    incidents = [];
}
export function getIncidentById(incidentId) {
    return incidents.find(i => i.incident_id === incidentId);
}
//# sourceMappingURL=pagerduty.js.map