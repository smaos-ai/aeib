import { Router } from 'express';
import { evaluateLatencyAlert, evaluateErrorRateAlert, evaluateComplianceAlert, getAlertHistory } from '../../lib/alerts';
const router = Router();
router.post('/evaluate/latency', (req, res) => {
    const { p95, threshold } = req.body;
    if (typeof p95 !== 'number' || typeof threshold !== 'number') {
        res.status(400).json({ error: 'Invalid latency values' });
        return;
    }
    const triggered = evaluateLatencyAlert(p95, threshold);
    res.json({ triggered, p95, threshold, type: 'latency' });
});
router.post('/evaluate/error-rate', (req, res) => {
    const { rate, threshold } = req.body;
    if (typeof rate !== 'number' || typeof threshold !== 'number') {
        res.status(400).json({ error: 'Invalid error rate values' });
        return;
    }
    const triggered = evaluateErrorRateAlert(rate, threshold);
    res.json({ triggered, rate, threshold, type: 'error_rate' });
});
router.post('/evaluate/compliance', (req, res) => {
    const { score, threshold } = req.body;
    if (typeof score !== 'number' || typeof threshold !== 'number') {
        res.status(400).json({ error: 'Invalid compliance values' });
        return;
    }
    const triggered = evaluateComplianceAlert(score, threshold);
    res.json({ triggered, score, threshold, type: 'compliance' });
});
router.get('/history', (req, res) => {
    const history = getAlertHistory();
    res.json({ alerts: history, count: history.length });
});
export default router;
//# sourceMappingURL=alerts.js.map