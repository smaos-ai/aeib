# Vision API Deployment & Operations

## Quick Start (localhost:8000)

```bash
cd services/planet-dashboard
bash deploy_localhost.sh
```

Verify:
```bash
curl http://localhost:8000/health
```

## Docker Deployment

**Architecture:**
- Python 3.11 + FastAPI + Uvicorn
- Pure-Python VisionAPI backend

**Build:**
```bash
cd services/planet-dashboard
docker-compose -f docker/docker-compose.yml build
```

**Run:**
```bash
docker-compose -f docker/docker-compose.yml up -d
```

**Logs:**
```bash
docker-compose -f docker/docker-compose.yml logs -f vision-api
```

**Stop:**
```bash
docker-compose -f docker/docker-compose.yml down
```

## API Endpoints

### POST /v1/govern

Governance decision endpoint (fail-closed).

**Request:**
```json
{
  "request_id": "req-001",
  "action": "read_file",
  "blast_radius": 0.1,
  "user_id": "user-1",
  "app_id": "app-1",
  "human_approved": false
}
```

**Response (Approved):**
```json
{
  "approved": true,
  "charge_amount": 100,
  "merkle_proof": {
    "merkle_root": "abc123...",
    "timestamp": "2026-06-04T12:00:00Z",
    "decision_id": "req-001",
    "approved_by": null,
    "auto_approved": true
  },
  "error": null,
  "reason": "Approved (risk: LOW)",
  "request_id": "req-001",
  "timestamp": "2026-06-04T12:00:00.123Z"
}
```

**Response (Blocked):**
```json
{
  "approved": false,
  "charge_amount": 0,
  "merkle_proof": null,
  "error": "HumanGateRequired",
  "reason": "Request requires human approval for risk level HIGH",
  "request_id": "req-002",
  "timestamp": "2026-06-04T12:00:01.456Z"
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "uptime_seconds": 123.45,
  "requests_processed": 4567
}
```

### GET /metrics

Performance metrics endpoint.

**Response:**
```json
{
  "uptime_seconds": 123.45,
  "requests_processed": 4567,
  "avg_request_time_ms": 27.1
}
```

## Load Testing

Run load test locally:

```bash
cd services/planet-dashboard
bash run_load_test.sh
```

**Target SLO:**
- Throughput: 1,000+ req/sec
- p99 latency: <100ms
- p95 latency: <50ms

**Expected Results (100 concurrent users, 60s test):**
```
Total Requests:      6,000+
Success Rate:        100%
Avg Latency:         ~30ms
p95 Latency:         ~50ms
p99 Latency:         ~80ms
```

## Monitoring

### Health Checks

```bash
# Every 10 seconds, timeout 5s, fail after 3 retries
docker-compose -f docker/docker-compose.yml ps
```

### Logs

```bash
# Real-time logs
docker-compose -f docker/docker-compose.yml logs -f

# Last 100 lines
docker-compose -f docker/docker-compose.yml logs --tail=100
```

### Metrics

```bash
# Hit metrics endpoint
curl http://localhost:8000/metrics | jq
```

## Troubleshooting

### Issue: Container fails to start

**Check logs:**
```bash
docker-compose -f docker/docker-compose.yml logs vision-api
```

**Common causes:**
- Missing dependencies: `pip install -r requirements.txt`
- Port 8000 already in use: `lsof -i :8000`
- Python version incompatibility: Requires Python 3.11+

### Issue: High latency (p99 >100ms)

**Causes:**
- Too many concurrent users (scale horizontally)
- Insufficient CPU/memory (increase Docker resource limits)
- Network bottleneck (check Docker network)

**Solution:**
```yaml
# docker-compose.yml
services:
  vision-api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

### Issue: Governance decisions incorrect

**Check:**
1. Is `blast_radius` correctly calculated? (should be 0.0-1.0)
2. Is `human_approved` flag being set correctly?
3. Review logs: `docker-compose logs vision-api | grep "Govern"`

## Integration with AP2 Ledger

When `result.approved == True`:
1. Charge user's AP2 ledger: `charge_amount` units
2. Store `merkle_proof` for audit trail
3. Log `decision_id` for traceability

When `result.approved == False`:
1. No charge (fail-closed)
2. Return error to user
3. Log reason in audit trail

**Pseudo-code:**
```python
result = api.govern(request)

if result.approved:
    # Charge AP2 ledger
    ledger.charge(user_id, result.charge_amount)
    # Store proof
    audit_log.append(result.merkle_proof)
else:
    # No charge, fail-closed
    print(f"Request blocked: {result.error}")
```

## Scaling

**Horizontal scaling:**
```yaml
# docker-compose.yml
services:
  vision-api-1:
    build: .
    ports:
      - "8000:8000"
  vision-api-2:
    build: .
    ports:
      - "8001:8001"
  vision-api-3:
    build: .
    ports:
      - "8002:8002"

  # Load balancer (optional)
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```

## Production Checklist

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Run integration tests: `pytest test_pyo3_integration.py -v`
- [ ] Run load test: `bash run_load_test.sh`
- [ ] Verify p99 latency <100ms
- [ ] Verify zero-charge on rejection (fail-closed)
- [ ] Deploy to Docker: `docker-compose up -d`
- [ ] Health check passes: `curl /health`
- [ ] Test `/v1/govern` endpoint
- [ ] Monitor logs: `docker-compose logs -f`
- [ ] Audit trail populated: `curl /metrics`

## References

- API Guide: `docs/integration/HUMANGATE_VISION_API_GUIDE.md`
- Test suite: `services/planet-dashboard/test_pyo3_integration.py`
- Load test: `services/planet-dashboard/load_test_locust.py`
