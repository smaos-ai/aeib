# SMAOS 5-Year Financial Model

## Revenue Projections

| Year | Customers | ARR (€) | Growth | Notes |
|------|-----------|---------|--------|-------|
| Y1 | 3 | 1.11M | Baseline | 3 pilots (hotel/glass/school) × €370K |
| Y2 | 50 | 8.5M | 665% | Enterprise sales team, market awareness |
| Y3 | 150 | 16M | 88% | Market penetration, partnerships |
| Y4 | 300 | 28M | 75% | Annex I enforcement, scaling |
| Y5 | 500 | 42M | 50% | Market maturity, premium pricing |

## Unit Economics

**Customer Acquisition Cost (CAC):**
- Sales salary: €100K/year, closes 5 deals/year
- Sales ops, travel, marketing: €50K/year
- Total CAC: €30K per customer (€150K cost ÷ 5 deals)
- Refined: Large enterprises €10K CAC (high LTV), SMEs €30K CAC (low LTV)

**Lifetime Value (LTV):**
- Contract length: 3 years (typical enterprise)
- Monthly fee: €5K-30K (average €10K)
- Annual retention: 95% (low churn, compliance non-negotiable)
- 3-year LTV: €180K (€10K × 12 × 1.5 retention multiplier)

**LTV/CAC Ratio:**
- Enterprise: €180K LTV ÷ €10K CAC = 18x (exceptional)
- SME: €60K LTV ÷ €30K CAC = 2x (manageable)
- Blended: 8x (well above 3x threshold)

**Payback Period:**
- Monthly revenue per customer: €10K
- CAC: €30K
- Payback: 3 months (revenue covers CAC in Q1)

## Gross Margin

**Cost Structure (per customer):**
- Infrastructure (Docker, GPU, monitoring): €1K/month
- Support staff (0.2 FTE per 50 customers): €2K/month
- Licensing (pgvector, Claude API): €1K/month
- Total cost of goods sold: €4K/month per customer

**Pricing & Margin:**
- Revenue per customer: €10K/month (average)
- COGS: €4K/month
- Gross margin: 60%

**Scaling margin:**
- As customer base scales, support ratio improves
- Y1 margin: 60%, Y5 margin: 78% (economies of scale)

## Operating Expenses

| Expense | Y1 | Y2 | Y3 | Y4 | Y5 |
|---------|----|----|----|----|-----|
| Sales & Marketing | 400K | 1.5M | 2.5M | 3M | 3.2M |
| R&D & Engineering | 600K | 2M | 3M | 4M | 4.5M |
| Operations & Admin | 200K | 500K | 800K | 1M | 1.2M |
| **Total OpEx** | **1.2M** | **4M** | **6.3M** | **8M** | **8.9M** |

## P&L

| Item | Y1 | Y2 | Y3 | Y4 | Y5 |
|------|----|----|----|----|-----|
| ARR (revenue) | 1.11M | 8.5M | 16M | 28M | 42M |
| COGS (60% Y1 → 22% Y5) | 670K | 2.4M | 4M | 6.2M | 9.2M |
| **Gross Profit** | **440K** | **6.1M** | **12M** | **21.8M** | **32.8M** |
| **Gross Margin %** | **40%** | **72%** | **75%** | **78%** | **78%** |
| OpEx | 1.2M | 4M | 6.3M | 8M | 8.9M |
| **EBITDA** | **-760K** | **2.1M** | **5.7M** | **13.8M** | **23.9M** |
| **EBITDA Margin %** | **-68%** | **25%** | **36%** | **49%** | **57%** |

## Cash Flow & Runway

**Series A Capital Raise: €2-3M**

**Assumptions:**
- Raise: €2.5M
- Burn rate Y1: €1.3M (OpEx - Gross Profit)
- Runway from Series A: 24 months
- Break-even: Month 18 (Q2 Y2)
- Path to Series B: €8.5M ARR, profitable unit economics

**Profitability:**
- Series A close: Month 0
- Monthly burn: -€108K (average Y1)
- Profitability achieved: Month 18
- Series B readiness: Month 20 (€8.5M ARR, 25% EBITDA margin)

## Series B & Beyond

**Series B (Month 24, Y2 end):**
- Revenue: €8.5M ARR
- EBITDA: €2.1M (25% margin)
- Growth rate: 88% YoY
- Raise: €10-15M (growth capital, geographic expansion)

**Path to Profitability:**
- Series A: -€760K (Y1 loss)
- Series B: +€2.1M (Y2 profit)
- Series C (optional): €5.7M+ (Y3+ margin expansion)

**Exit Valuation (Y5):**
- Revenue: €42M
- Multiples: SaaS 8-10x revenue, Enterprise 10-12x revenue
- Valuation: €336-504M (conservative 8x to aggressive 12x)
- Shareholder return: 100-200x Series A capital (€2.5M → €336-504M)

## Key Assumptions (Conservative)

1. **Customer growth:** Linear (not hockey-stick)
   - Assumes competitive entry, market saturation
   - Actual likely faster (regulatory enforcement drive)
2. **Pricing:** Flat €10K/month (not inflation-adjusted)
   - Actual likely €12-15K/month by Y5
3. **Churn:** 5% annual (low but realistic for compliance)
   - Actual likely 2-3% (non-discretionary spend)
4. **COGS:** 60% Y1 (edge-native is expensive to support)
   - Actual likely 40% (shared infrastructure, automation)

**Conservative margin:** If actual performs 20% better, EBITDA 40% higher by Y5.

## Funding Requirements Summary

| Stage | Capital | Purpose | Timeline | Runway |
|-------|---------|---------|----------|--------|
| Series A | €2-3M | Sales, engineering, compliance | 0-18 months | 24-month |
| Series B | €10-15M | Growth, geographic expansion | 18-36 months | 24-month |
| Series C (optional) | €20-30M | M&A, margin expansion, exit prep | 36-48 months | - |

**Bottom line:** Break-even by Month 18. Path to €42M ARR in 5 years. 100-200x shareholder return if exit at Y5 valuation.
