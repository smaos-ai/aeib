import express from 'express';
import { initMetrics } from './lib/prometheus';
import { initSlack } from './lib/slack';
import { initPagerDuty } from './lib/pagerduty';
import { initELK } from './lib/elk';
import { initAlerts } from './lib/alerts';
import metricsRouter from './api/routes/metrics';
import alertsRouter from './api/routes/alerts';
import incidentsRouter from './api/routes/incidents';
import runbooksRouter from './api/routes/runbooks';
const app = express();
const PORT = process.env.PORT || 3000;
// Middleware
app.use(express.json());
// Initialize all systems
initMetrics();
initSlack(process.env.SLACK_TOKEN || 'test-token');
initPagerDuty(process.env.PAGERDUTY_API_KEY || 'test-api-key');
initELK();
initAlerts();
// Health check
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        uptime: process.uptime()
    });
});
// API Routes
app.use('/api/metrics', metricsRouter);
app.use('/api/alerts', alertsRouter);
app.use('/api/incidents', incidentsRouter);
app.use('/api/runbooks', runbooksRouter);
// 404 handler
app.use((req, res) => {
    res.status(404).json({
        error: 'Not found',
        path: req.path,
        method: req.method
    });
});
// Error handler
app.use((err, req, res, next) => {
    console.error('Error:', err);
    res.status(500).json({
        error: 'Internal server error',
        message: err.message
    });
});
export { app };
// Start server if this is the main module
if (require.main === module) {
    app.listen(PORT, () => {
        console.log(`SISS Production Ops server running on port ${PORT}`);
    });
}
//# sourceMappingURL=server.js.map