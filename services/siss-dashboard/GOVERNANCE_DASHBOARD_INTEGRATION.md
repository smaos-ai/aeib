# Axiom Planet Governance Dashboard — React/Next.js Integration Guide

## Overview

This document outlines the React/Next.js migration of the Streamlit governance dashboard, including component architecture, Vision API integration, and deployment readiness.

## Project Structure

```
app/
├── governance-dashboard/
│   └── page.tsx                 # Main dashboard page
├── components/
│   ├── charts/
│   │   ├── AP2Distribution.tsx       # (1) Pie chart - AP2 token splits
│   │   ├── PSIDriftGauge.tsx         # (4) Gauge chart - Model drift monitoring
│   │   └── MerkleChainVisualizer.tsx # (3) Merkle chain audit trail
│   ├── tables/
│   │   └── DecisionOwnershipTable.tsx # (2) Ed25519 signature table
│   ├── metrics/
│   │   └── GovernanceROI.tsx         # (5) ROI metrics + fines avoided
│   └── layout/
│       ├── ComplianceExport.tsx      # (6) JSON/CSV export button
│       └── KPICards.tsx              # Summary metrics
lib/
├── api-client.ts                # Vision API polling client
└── hooks.ts                     # Custom React hooks for data
```

## Component Feature Mapping

### 1. AP2Distribution.tsx
**Migrated from:** `st.plotly_chart(fig_pie, ...)`
**Features:**
- Donut pie chart with 5 segments (Creator/Data/Planet/Infra/Architect)
- Real-time updates via polling
- Tooltip shows exact USD amounts
- Color-coded segments matching Streamlit original

**Props:**
```tsx
interface AP2DistributionProps {
  data: {
    creator: number;
    data: number;
    planet: number;
    infra: number;
    architect: number;
  };
}
```

### 2. DecisionOwnershipTable.tsx
**Migrated from:** `st.dataframe(df[...], ...)`
**Features:**
- 8-column table: Timestamp, Capsule Hash, Risk Level, Approval Status, **Ed25519 Public Key**, Verification, Amount, Merkle Root
- Sortable columns (future enhancement)
- Risk-level color coding
- Truncated hashes with full values on hover
- Last 15 capsules displayed
- Ed25519 public key in dedicated column (cryptographic non-repudiation proof)

**Props:**
```tsx
interface DecisionOwnershipTableProps {
  capsules: Capsule[];
}
```

### 3. MerkleChainVisualizer.tsx
**Migrated from:** `st.dataframe(df_chain, ...)`
**Features:**
- Linear visualization of last 10 Merkle roots
- Numbered chain links
- Current root highlighted
- Chain depth counter
- Full root shown on hover
- Immutable audit trail confirmation

**Props:**
```tsx
interface MerkleChainVisualizerProps {
  chain: string[];
}
```

### 4. PSIDriftGauge.tsx
**Migrated from:** `go.Figure(go.Indicator(...))`
**Features:**
- Custom gauge visualization (3-zone: green/yellow/red)
- Real-time PSI value (0.0–0.5 range)
- 24-hour trend line chart
- Thresholds: PSI < 0.1 (stable), 0.1–0.25 (caution), > 0.25 (alert)
- Status alerts with action text
- Recharts integration

**Props:**
```tsx
interface PSIDriftGaugeProps {
  currentPSI: number;
  history?: Array<{ time: number; psi: number }>;
}
```

### 5. GovernanceROI.tsx
**Migrated from:** Calculated metrics in Streamlit footer
**Features:**
- 3-card layout: Unsafe Actions Prevented, Fines Avoided, Creator Royalties
- Calculates avoided fines: `blocked_count × €35M × 0.012 factor`
- ROI multiplier: `fines_avoided / creator_royalties`
- Compliance rate (always 100%)
- Summary stats grid
- EU AI Act Article 12 messaging

**Props:**
```tsx
interface GovernanceROIProps {
  highRiskBlocked: number;
  highRiskApproved: number;
  creatorRoyalties: number;
  finePerViolation?: number;  // Default: €35M
  blockedFineFactor?: number;  // Default: 0.012
}
```

### 6. ComplianceExport.tsx
**Migrated from:** `st.download_button(...)`
**Features:**
- Dual-format export: JSON + CSV
- JSON includes metadata: timestamp, merkle root, compliance standard
- CSV includes all capsule data with proper escaping
- File naming: `compliance_report_YYYY-MM-DD.{json|csv}`
- EU AI Act / ISO 42001 compliance badges
- Ed25519 signature scheme notation
- Disabled state when no capsules

**Props:**
```tsx
interface ComplianceExportProps {
  capsules: Capsule[];
  merkleRoot?: string;
}
```

## Vision API Integration

### API Client (`lib/api-client.ts`)

**Endpoint:** `http://localhost:8000/v1/ledger`

**Response Format:**
```typescript
interface LedgerResponse {
  transactions: Capsule[];
  current_merkle_root: string;
  total_capsules: number;
}

interface Capsule {
  capsule_hash: string;
  risk_level: 'low' | 'medium' | 'high';
  human_approved: boolean;
  ed25519_public_key?: string;
  ed25519_verified?: boolean;
  charge_amount: number;
  split: {
    creator: number;
    data: number;
    planet: number;
    infra: number;
    architect: number;
  };
  timestamp: number;
  merkle_root: string;
}
```

**Polling Strategy:**
- Default interval: 5000ms (configurable via `NEXT_PUBLIC_POLL_INTERVAL`)
- Uses SWR library for caching and request deduplication
- Automatic retry on failure
- Graceful fallback to mock data in demo mode

### Hooks (`lib/hooks.ts`)

**`useLedger(pollInterval = 5000)`**
- Fetches ledger data with configurable interval
- Returns: `{ ledger, isLoading, error, mutate }`
- Handles real API + mock fallback

**`useCapsuleMetrics(capsules)`**
- Computes all dashboard metrics from capsule array
- Returns aggregated: totals, AP2 split, risk counts, approval rate, merkle chain

**`generatePSIDrift()`**
- Simulates realistic PSI drift values (0.0–0.5)
- Used in demo mode when real model metrics unavailable

**`generatePSIHistory(hours = 24)`**
- Generates mock 24-hour trend data for gauge chart

## Deployment Readiness Checklist

### Prerequisites
- Node.js 18+
- Next.js 16.2.6
- React 19.2.4
- Recharts 2.10.3
- Axios 1.6.0
- SWR 2.2.0

### Installation & Setup

```bash
# Install dependencies
npm install

# Set environment variables (.env or .env.local)
NEXT_PUBLIC_API_BASE=http://localhost:8000/v1
NEXT_PUBLIC_POLL_INTERVAL=5000
NEXT_PUBLIC_DEMO_MODE=true  # Set to false for production

# Development
npm run dev

# Production build
npm run build
npm start
```

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000/v1` | Vision API endpoint |
| `NEXT_PUBLIC_POLL_INTERVAL` | `5000` | Polling frequency (ms) |
| `NEXT_PUBLIC_DEMO_MODE` | `true` | Enable mock data fallback |

### Docker Deployment

```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: governance-dashboard
spec:
  replicas: 3
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
        image: sovereignnexus/governance-dashboard:latest
        ports:
        - containerPort: 3000
        env:
        - name: NEXT_PUBLIC_API_BASE
          value: "https://api.axiom.planet/v1"
        - name: NEXT_PUBLIC_POLL_INTERVAL
          value: "5000"
        livenessProbe:
          httpGet:
            path: /governance-dashboard
            port: 3000
          initialDelaySeconds: 10
          periodSeconds: 10
```

## Testing

### Component Unit Tests

```bash
npm test
```

Test files should be co-located with components:
```
app/components/charts/AP2Distribution.tsx
app/components/charts/AP2Distribution.test.tsx
```

### Integration Tests

```bash
npm run test:integration
```

Tests Vision API mocking, data flow, and aggregation.

### E2E Tests (Recommended Addition)

```bash
npm install -D playwright
npx playwright install
```

Example E2E test:
```typescript
import { test, expect } from '@playwright/test';

test('dashboard loads and displays metrics', async ({ page }) => {
  await page.goto('http://localhost:3000/governance-dashboard');
  
  // Wait for KPI cards to load
  await expect(page.locator('text=Today\'s Capsules')).toBeVisible();
  
  // Verify AP2 distribution chart renders
  await expect(page.locator('svg')).toBeTruthy();
  
  // Check export button is clickable
  const exportBtn = page.locator('button:has-text("Download JSON Report")');
  await expect(exportBtn).toBeEnabled();
});
```

## Performance Considerations

1. **Polling Optimization**
   - Uses SWR for request deduplication
   - Configurable interval (default 5s)
   - Consider longer intervals (30-60s) for production

2. **Chart Rendering**
   - Recharts components memoized
   - History limited to 24 hours (reasonable memory footprint)
   - Pie chart truncated to non-zero segments

3. **Table Rendering**
   - Limited to last 15 capsules (pagination recommended for production)
   - Virtual scrolling recommended for large datasets

4. **Code Splitting**
   - Each component is a separate module
   - Recharts imported dynamically to reduce bundle size

## Migration From Streamlit

### Removed Features
- Auto-refresh via `st.rerun()` — replaced with SWR polling
- Sidebar state management — converted to React context (optional)
- Plotly interactivity — Recharts has basic interactivity

### Enhanced Features
- **Server-side state:** Can integrate with Next.js API routes
- **WebSocket support:** Ready for real-time updates (future)
- **Flexible data sources:** Supports SQL, GraphQL, REST APIs
- **Custom styling:** Full CSS-in-JS / Tailwind control

### Data Flow Diagram

```
Vision API (localhost:8000/v1/ledger)
         ↓
    Axios client
         ↓
    useLedger() hook
         ↓
    useCapsuleMetrics()
         ↓
    Component Props
         ↓
    Recharts/HTML rendering
```

## Future Enhancements

1. **WebSocket Support** — Replace polling with real-time streaming
   ```typescript
   // lib/websocket-client.ts
   export class VisionWebSocketClient {
     connect(url: string) { ... }
     onLedgerUpdate(callback) { ... }
   }
   ```

2. **Historical Analytics** — Add time-range filters
   ```tsx
   <DateRangePicker onSelect={(range) => filterCapsules(range)} />
   ```

3. **Pagination** — Replace hardcoded "last 15" with full table nav
   ```tsx
   <DataTable data={capsules} rowsPerPage={50} />
   ```

4. **Real-time Alerts** — Toast notifications for high-risk events
   ```tsx
   if (newCapsule.risk_level === 'high' && !newCapsule.human_approved) {
     showAlert('High-risk action blocked!');
   }
   ```

5. **Dark Mode Toggle** — Already built with Tailwind (`dark:` classes)

6. **Export Scheduling** — Automatic compliance report generation
   ```typescript
   // API route: /api/exports/schedule
   POST /api/exports/schedule {
     frequency: 'daily' | 'weekly' | 'monthly',
     recipients: ['compliance@axiom.planet']
   }
   ```

## Troubleshooting

### Vision API Connection Failed
- Ensure `http://localhost:8000/v1/ledger` is accessible
- Check `NEXT_PUBLIC_API_BASE` environment variable
- Set `NEXT_PUBLIC_DEMO_MODE=true` to use mock data

### Charts Not Rendering
- Verify Recharts is installed: `npm ls recharts`
- Check browser console for errors
- Ensure data structure matches interface definitions

### Table Truncation Issues
- Increase table height in `DecisionOwnershipTable.tsx`
- Add virtual scrolling library: `react-window`

### Slow Polling
- Increase `NEXT_PUBLIC_POLL_INTERVAL` (e.g., 30000ms)
- Implement request caching in backend API

## Contact & Support

For questions on:
- **Component API:** See JSDoc comments in each component file
- **Vision API integration:** Refer to `.claude/VISION_API_INTEGRATION_SPEC.md`
- **Deployment:** Check `.claude/DEPLOYMENT_48H_CHECKLIST.md`
