import { Router } from 'express';
import { getRunbook, listRunbooks } from '../../lib/runbooks';
const router = Router();
router.get('/', (req, res) => {
    const runbooks = listRunbooks();
    res.json({ runbooks, count: runbooks.length });
});
router.get('/:alert_type', (req, res) => {
    const { alert_type } = req.params;
    const runbook = getRunbook(alert_type);
    res.json({
        alert_type,
        runbook
    });
});
export default router;
//# sourceMappingURL=runbooks.js.map