import { randomUUID } from 'crypto';
import { IncidentResponse, PlaybookAction, ThreatLevel } from './types';

interface PlaybookInput {
  name: string;
  threatLevel: ThreatLevel;
  description: string;
}

export class PlaybookService {
  private playbooks: Map<string, PlaybookData> = new Map();
  private responses: Map<string, IncidentResponse> = new Map();

  createPlaybook(input: PlaybookInput): PlaybookData {
    const playbook: PlaybookData = {
      id: randomUUID(),
      ...input,
      actions: [],
      enabled: true
    };

    this.playbooks.set(playbook.id, playbook);
    return playbook;
  }

  selectPlaybook(threatLevel: ThreatLevel): PlaybookData | undefined {
    const candidates = Array.from(this.playbooks.values())
      .filter(p => p.enabled && p.threatLevel === threatLevel);

    return candidates.length > 0 ? candidates[0] : undefined;
  }

  addAction(playbookId: string, action: Omit<PlaybookAction, 'id'>): void {
    const playbook = this.playbooks.get(playbookId);
    if (!playbook) return;

    const fullAction: PlaybookAction = {
      id: randomUUID(),
      ...action
    };

    playbook.actions.push(fullAction);
  }

  async executePlaybook(playbookId: string): Promise<IncidentResponse> {
    const playbook = this.playbooks.get(playbookId);
    if (!playbook) {
      throw new Error(`Playbook ${playbookId} not found`);
    }

    const response: IncidentResponse = {
      incidentId: randomUUID(),
      playbookId,
      threatLevel: playbook.threatLevel,
      actions: [],
      status: 'in-progress',
      createdAt: new Date()
    };

    // Execute each action
    for (const action of playbook.actions) {
      const executedAction: PlaybookAction = {
        ...action,
        status: 'in-progress'
      };

      response.actions.push(executedAction);

      // Simulate action execution
      await this.executeAction(action);

      executedAction.status = 'completed';
      executedAction.result = `${action.name} completed successfully`;
    }

    response.status = 'completed';
    response.completedAt = new Date();

    this.responses.set(response.incidentId, response);
    return response;
  }

  private async executeAction(action: PlaybookAction): Promise<void> {
    // Simulate action execution
    return new Promise(resolve => setTimeout(resolve, Math.random() * 100));
  }

  getPlaybook(playbookId: string): PlaybookData | undefined {
    return this.playbooks.get(playbookId);
  }

  getAllPlaybooks(): PlaybookData[] {
    return Array.from(this.playbooks.values());
  }

  enablePlaybook(playbookId: string): void {
    const playbook = this.playbooks.get(playbookId);
    if (playbook) {
      playbook.enabled = true;
    }
  }

  disablePlaybook(playbookId: string): void {
    const playbook = this.playbooks.get(playbookId);
    if (playbook) {
      playbook.enabled = false;
    }
  }

  getResponse(incidentId: string): IncidentResponse | undefined {
    return this.responses.get(incidentId);
  }

  getAllResponses(): IncidentResponse[] {
    return Array.from(this.responses.values());
  }
}

interface PlaybookData {
  id: string;
  name: string;
  threatLevel: ThreatLevel;
  description: string;
  actions: PlaybookAction[];
  enabled: boolean;
}
