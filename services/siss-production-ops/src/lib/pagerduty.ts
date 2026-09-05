import { v4 as uuidv4 } from 'uuid';

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

let apiKey: string = '';
let incidents: IncidentResponse[] = [];

export function initPagerDuty(token: string): void {
  apiKey = token;
}

function severityToUrgency(severity: string): 'high' | 'low' {
  if (severity === 'critical' || severity === 'high') {
    return 'high';
  }
  return 'low';
}

export async function createIncident(
  request: IncidentRequest
): Promise<IncidentResponse> {
  const incident: IncidentResponse = {
    ...request,
    incident_id: `PD-${uuidv4()}`,
    status: 'triggered',
    urgency: severityToUrgency(request.severity),
    created_at: new Date().toISOString()
  };

  incidents.push(incident);
  return incident;
}

export async function resolveIncident(
  incidentId: string,
  resolution_notes: string
): Promise<void> {
  const incident = incidents.find(i => i.incident_id === incidentId);
  if (incident) {
    incident.status = 'resolved';
    incident.resolved_at = new Date().toISOString();
    incident.resolution_notes = resolution_notes;
  }
}

export function getIncidents(): IncidentResponse[] {
  return [...incidents];
}

export function clearIncidents(): void {
  incidents = [];
}

export function getIncidentById(incidentId: string): IncidentResponse | undefined {
  return incidents.find(i => i.incident_id === incidentId);
}
