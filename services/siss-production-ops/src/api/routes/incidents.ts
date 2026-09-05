import { Router, Request, Response } from 'express';
import {
  createIncident,
  resolveIncident,
  getIncidents,
  getIncidentById
} from '../../lib/pagerduty';

const router = Router();

router.post('/create', async (req: Request, res: Response) => {
  const { title, severity, service_id, description } = req.body;

  if (!title || !severity || !service_id || !description) {
    res.status(400).json({ error: 'Missing required fields' });
    return;
  }

  try {
    const incident = await createIncident({
      title,
      severity,
      service_id,
      description
    });
    res.status(201).json(incident);
  } catch (error) {
    res.status(500).json({ error: 'Failed to create incident' });
  }
});

router.post('/:incident_id/resolve', async (req: Request, res: Response) => {
  const { incident_id } = req.params;
  const { resolution_notes } = req.body;

  if (!resolution_notes) {
    res.status(400).json({ error: 'Resolution notes required' });
    return;
  }

  try {
    await resolveIncident(incident_id, resolution_notes);
    const incident = getIncidentById(incident_id);
    res.json(incident);
  } catch (error) {
    res.status(500).json({ error: 'Failed to resolve incident' });
  }
});

router.get('/', (req: Request, res: Response) => {
  const incidents = getIncidents();
  res.json({ incidents, count: incidents.length });
});

router.get('/:incident_id', (req: Request, res: Response) => {
  const { incident_id } = req.params;
  const incident = getIncidentById(incident_id);

  if (!incident) {
    res.status(404).json({ error: 'Incident not found' });
    return;
  }

  res.json(incident);
});

export default router;
