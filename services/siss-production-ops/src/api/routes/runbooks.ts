import { Router, Request, Response } from 'express';
import { getRunbook, listRunbooks } from '../../lib/runbooks';

const router = Router();

router.get('/', (req: Request, res: Response) => {
  const runbooks = listRunbooks();
  res.json({ runbooks, count: runbooks.length });
});

router.get('/:alert_type', (req: Request, res: Response) => {
  const { alert_type } = req.params;
  const runbook = getRunbook(alert_type);

  res.json({
    alert_type,
    runbook
  });
});

export default router;
