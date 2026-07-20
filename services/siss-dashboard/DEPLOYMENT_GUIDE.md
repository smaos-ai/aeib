# Governance Dashboard — Deployment & Operations Guide

## Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                   Client Browser                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Next.js App (React 19)                              │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │ Governance Dashboard (/governance-dashboard)  │  │  │
│  │  │                                                │  │  │
│  │  │  Components:                                  │  │  │
│  │  │  • KPICards (4 metrics)                       │  │  │
│  │  │  • AP2Distribution (Recharts pie)            │  │  │
│  │  │  • PSIDriftGauge (custom gauge + trend)      │  │  │
│  │  │  • MerkleChainVisualizer (chain explorer)    │  │  │
│  │  │  • DecisionOwnershipTable (Ed25519 pubkeys)  │  │  │
│  │  │  • GovernanceROI (metrics cards)             │  │  │
│  │  │  • ComplianceExport (JSON/CSV download)      │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │                                                       │  │
│  │  Hooks & Utilities:                                 │  │
│  │  • useLedger() — SWR polling                        │  │
│  │  • useCapsuleMetrics() — data aggregation          │  │
│  │  • visionAPIClient — Axios HTTP                     │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
                           ↓ HTTP/HTTPS
              ┌─────────────────────────────┐
              │   Vision API Server          │
              │ localhost:8000/v1/ledger    │
              │ (future: ws://...)           │
              └─────────────────────────────┘
                           ↓
              ┌─────────────────────────────┐
              │   Axiom Protocol Stack      │
              │ • BaselineCapsule           │
              │ • MongeGapGovernor          │
              │ • AP2 Ledger                │
              │ • Merkle-DAG                │
              └─────────────────────────────┘
```

## Deployment Targets

### 1. Local Development

```bash
# Prerequisites
node --version  # v18+
npm --version   # v10+

# Setup
cd /path/to/siss-dashboard
npm install

# Run
npm run dev
# Dashboard available at: http://localhost:3000/governance-dashboard

# Watch & live reload enabled
```

### 2. Docker Container

**Build Image:**
```bash
docker build -t governance-dashboard:latest .

# Or with args
docker build \
  --build-arg API_BASE=http://localhost:8000/v1 \
  -t governance-dashboard:latest .
```

**Run Container:**
```bash
docker run -d \
  -p 3000:3000 \
  -e NEXT_PUBLIC_API_BASE=http://api:8000/v1 \
  -e NEXT_PUBLIC_POLL_INTERVAL=5000 \
  --name governance-dashboard \
  governance-dashboard:latest
```

**Docker Compose:**
```yaml
version: '3.8'
services:
  dashboard:
    build: .
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_BASE: http://vision-api:8000/v1
      NEXT_PUBLIC_POLL_INTERVAL: 5000
    depends_on:
      - vision-api
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/governance-dashboard"]
      interval: 10s
      timeout: 5s
      retries: 3

  vision-api:
    image: axiom/vision-api:latest
    ports:
      - "8000:8000"
```

### 3. Kubernetes Deployment

**Create namespace:**
```bash
kubectl create namespace governance
```

**Deploy with Helm:**
```bash
helm install governance-dashboard ./helm/governance-dashboard \
  --namespace governance \
  --values helm/values.yaml \
  --set image.repository=sovereignnexus/governance-dashboard \
  --set image.tag=1.0.0
```

**Manual YAML deployment:**
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: governance-dashboard
  namespace: governance
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: governance-dashboard
  template:
    metadata:
      labels:
        app: governance-dashboard
    spec:
      containers:
      - name: dashboard
        image: sovereignnexus/governance-dashboard:1.0.0
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 3000
          name: http
        env:
        - name: NEXT_PUBLIC_API_BASE
          valueFrom:
            configMapKeyRef:
              name: dashboard-config
              key: api-base
        - name: NEXT_PUBLIC_POLL_INTERVAL
          value: "5000"
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
        livenessProbe:
          httpGet:
            path: /governance-dashboard
            port: 3000
          initialDelaySeconds: 15
          periodSeconds: 20
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /governance-dashboard
            port: 3000
          initialDelaySeconds: 10
          periodSeconds: 10
          failureThreshold: 2
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          runAsNonRoot: true
          runAsUser: 1000
---
apiVersion: v1
kind: Service
metadata:
  name: governance-dashboard
  namespace: governance
spec:
  selector:
    app: governance-dashboard
  type: LoadBalancer
  ports:
  - protocol: TCP
    port: 80
    targetPort: 3000
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: dashboard-config
  namespace: governance
data:
  api-base: "https://api.axiom.planet/v1"
```

**Deploy:**
```bash
kubectl apply -f deployment.yaml
kubectl rollout status deployment/governance-dashboard -n governance
```

### 4. Vercel (Recommended for Next.js)

**1. Push to GitHub:**
```bash
git push origin main
```

**2. Connect to Vercel:**
```bash
vercel --project governance-dashboard
```

**3. Set Environment Variables:**
```bash
vercel env add NEXT_PUBLIC_API_BASE
# Prompt: https://api.axiom.planet/v1

vercel env add NEXT_PUBLIC_POLL_INTERVAL
# Prompt: 5000
```

**4. Deploy:**
```bash
vercel --prod
```

**Dashboard available at:** `https://governance-dashboard.vercel.app`

## Monitoring & Observability

### Health Checks

**Add health check endpoint:**
```typescript
// app/api/health/route.ts
export async function GET() {
  try {
    const health = {
      status: 'healthy',
      timestamp: new Date().toISOString(),
      checks: {
        vision_api: await checkVisionAPI(),
        database: await checkDatabase(),
        memory: process.memoryUsage().heapUsed < 512 * 1024 * 1024
      }
    };
    
    const allHealthy = Object.values(health.checks).every(Boolean);
    return Response.json(health, {
      status: allHealthy ? 200 : 503
    });
  } catch (error) {
    return Response.json({ error: 'Health check failed' }, { status: 503 });
  }
}
```

### Logging

**Configure logging (future):**
```typescript
// lib/logger.ts
import pino from 'pino';

export const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  transport: {
    target: 'pino-pretty',
    options: { colorize: true }
  }
});
```

### Metrics

**Track with Prometheus (optional integration):**
```typescript
// lib/metrics.ts
import { register, Counter, Gauge } from 'prom-client';

export const ledgerFetchCount = new Counter({
  name: 'ledger_fetch_total',
  help: 'Total ledger fetch requests',
  labelNames: ['status']
});

export const capsuleCount = new Gauge({
  name: 'capsules_total',
  help: 'Total capsules in ledger'
});
```

## Performance Optimization

### 1. Image Optimization
```typescript
import Image from 'next/image';

<Image
  src="/axiom-logo.png"
  alt="Axiom Planet"
  width={80}
  height={80}
  priority={true}
/>
```

### 2. Code Splitting
Components are automatically code-split by Next.js. To force dynamic imports:
```typescript
import dynamic from 'next/dynamic';

const MerkleChainVisualizer = dynamic(
  () => import('@/app/components/charts/MerkleChainVisualizer'),
  { ssr: false }
);
```

### 3. Caching Strategy
```typescript
// next.config.ts
export default {
  headers: async () => {
    return [
      {
        source: '/governance-dashboard',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=60, s-maxage=300'
          }
        ]
      }
    ];
  }
};
```

### 4. Database Connection Pooling
```typescript
// lib/prisma.ts (already configured)
import { PrismaClient } from '@prisma/client';

const globalForPrisma = global as unknown as { prisma: PrismaClient };

export const prisma = globalForPrisma.prisma || new PrismaClient();

if (process.env.NODE_ENV !== 'production') {
  globalForPrisma.prisma = prisma;
}
```

## Rollback Procedures

### Docker Rollback
```bash
# Keep previous image versions tagged
docker tag governance-dashboard:1.0.0 governance-dashboard:1.0.0-backup

# Deploy new version
docker run -d governance-dashboard:1.1.0

# If issue detected, rollback:
docker stop <new-container-id>
docker run -d governance-dashboard:1.0.0-backup
```

### Kubernetes Rollback
```bash
# View rollout history
kubectl rollout history deployment/governance-dashboard -n governance

# Rollback to previous version
kubectl rollout undo deployment/governance-dashboard -n governance

# Rollback to specific revision
kubectl rollout undo deployment/governance-dashboard -n governance --to-revision=2
```

### Vercel Rollback
```bash
vercel rollback --prod
```

## Security Hardening

### CORS Configuration
```typescript
// next.config.ts
export default {
  headers: async () => {
    return [
      {
        source: '/api/(.*)',
        headers: [
          {
            key: 'Access-Control-Allow-Origin',
            value: process.env.ALLOWED_ORIGINS || 'https://axiom.planet'
          },
          {
            key: 'Access-Control-Allow-Methods',
            value: 'GET, POST, OPTIONS'
          }
        ]
      }
    ];
  }
};
```

### Content Security Policy
```typescript
// middleware.ts
import { NextResponse } from 'next/server';

export function middleware(request: Request) {
  const response = NextResponse.next();
  
  response.headers.set(
    'Content-Security-Policy',
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
  );
  
  response.headers.set('X-Content-Type-Options', 'nosniff');
  response.headers.set('X-Frame-Options', 'DENY');
  
  return response;
}
```

## CI/CD Pipeline (GitHub Actions Example)

```yaml
# .github/workflows/deploy.yml
name: Deploy Governance Dashboard

on:
  push:
    branches: [main, staging]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm ci
      - run: npm run lint
      - run: npm run test

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm ci
      - run: npm run build
      - uses: actions/upload-artifact@v3
        with:
          name: build
          path: .next/

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Vercel
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
        run: |
          npm install -g vercel
          vercel --prod --token $VERCEL_TOKEN
```

## Troubleshooting Deployment Issues

### Issue: Vision API Connection Timeout
**Solution:**
```bash
# Check API connectivity
curl -v http://localhost:8000/v1/ledger

# Update NEXT_PUBLIC_API_BASE in environment
NEXT_PUBLIC_API_BASE=https://api.axiom.planet/v1
```

### Issue: Memory Leak in Long-Running Instance
**Solution:**
- Implement periodic restart:
  ```bash
  # In Kubernetes, set a restartPolicy
  spec:
    template:
      spec:
        containers:
        - name: dashboard
          # Add memory monitoring
  ```
- Optimize SWR polling interval
- Check for circular dependencies in components

### Issue: Slow Initial Load
**Solution:**
```bash
# Analyze bundle size
npm run analyze

# Use dynamic imports
const MerkleChain = dynamic(() => import('...'), { ssr: false });

# Enable caching
NEXT_PUBLIC_CACHE_STRATEGY=swr
```

## Production Readiness Checklist

- [ ] Environment variables configured for production API
- [ ] SSL/TLS certificate installed (HTTPS enforced)
- [ ] CORS headers configured for allowed origins
- [ ] Database connection pooling enabled
- [ ] Monitoring and alerting configured
- [ ] Health checks passing
- [ ] Load testing completed (target: 1000 req/s)
- [ ] Security scan completed (OWASP Top 10)
- [ ] Backup and disaster recovery plan documented
- [ ] Runbook created for common issues
- [ ] Team trained on deployment process
- [ ] Auto-scaling configured (if cloud-hosted)
- [ ] CDN configured for static assets
- [ ] Rate limiting enabled on API routes

## Support & Escalation

For deployment issues:
1. Check health endpoint: `GET /api/health`
2. Review logs: `kubectl logs -f deployment/governance-dashboard`
3. Check Vision API connectivity
4. Verify environment variables
5. Escalate to platform team if unresolved
