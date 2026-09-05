import { Router } from 'express';
import { getMetricsExport, recordCpuUsage, recordMemoryUsage } from '../../lib/prometheus';
const router = Router();
router.get('/metrics', async (req, res) => {
    try {
        const metrics = await getMetricsExport();
        res.set('Content-Type', 'text/plain');
        res.send(metrics);
    }
    catch (error) {
        res.status(500).json({ error: 'Failed to export metrics' });
    }
});
router.post('/cpu', (req, res) => {
    const { value } = req.body;
    if (typeof value !== 'number') {
        res.status(400).json({ error: 'Invalid CPU value' });
        return;
    }
    recordCpuUsage(value);
    res.json({ success: true, cpu_usage: value });
});
router.post('/memory', (req, res) => {
    const { value } = req.body;
    if (typeof value !== 'number') {
        res.status(400).json({ error: 'Invalid memory value' });
        return;
    }
    recordMemoryUsage(value);
    res.json({ success: true, memory_usage: value });
});
export default router;
//# sourceMappingURL=metrics.js.map