// EU AI Act Annex III - High-Risk Hospitality Pilot
export const hospitalityAnnexIII = {
  id: 'hospitalityAnnexIII',
  label: 'KARP Hotel Pilot (EU AI Act Annex III)',
  domain: 'hospitality',
  intentFields: [
    { name: 'guestName', label: 'Guest Name', type: 'text', required: true },
    { name: 'dataCategory', label: 'Data Category', type: 'select', options: ['PII', 'Payment Info', 'Booking History', 'None'], required: true },
    { name: 'purpose', label: 'Purpose', type: 'select', options: ['Credit Assessment', 'Booking Verification', 'Loyalty Check', 'Generic Query'], required: true },
    { name: 'roomType', label: 'Room Type', type: 'text', required: false },
  ],
  toolCatalog: [
    { id: 'db_guest_lookup', label: 'Guest Database Lookup', toolName: 'db_query.guests', simulateFailure: false },
    { id: 'credit_check', label: 'Credit Scoring Check', toolName: 'credit_assessment.score', simulateFailure: true },
    { id: 'booking_history', label: 'Booking History Retrieval', toolName: 'booking.history_lookup', simulateFailure: false },
    { id: 'reserve_room', label: 'Reserve Room', toolName: 'booking.reserve', simulateFailure: false },
  ],
  riskRules: [
    {
      id: 'pii_detection',
      test: (fields) => fields.dataCategory === 'PII',
      classification: 'Annex III High-Risk Triggered',
      citation: `EU AI Act § Annex III, Article 14 (Human Oversight)
Clause: High-Risk AI Systems in Essential Services and Public Administration.
Personal data (PII) processing for credit assessment requires human authorization.
All decisions must be explainable and subject to human review before execution.
Reference: Regulation (EU) 2026/1744, Digital Omnibus on AI, enacted Jul 27, 2026.`,
      severity: 'block',
    },
    {
      id: 'credit_assessment',
      test: (fields) => fields.purpose === 'Credit Assessment',
      classification: 'Annex III High-Risk Triggered',
      citation: `EU AI Act § Annex III, Article 14 (Human Oversight)
Clause: Automated credit decisions are classified as high-risk.
Binding human approval required before any credit-affecting action is taken.
Reference: Regulation (EU) 2026/1744, Digital Omnibus on AI, enacted Jul 27, 2026.`,
      severity: 'block',
    },
  ],
  vetoCopy: {
    title: 'Human Authorization Required (Article 14)',
    bodyTemplate: (intent, matchedRules) => `This action triggers ${matchedRules.length} high-risk classification(s):
${matchedRules.map(r => `  • ${r.classification}`).join('\n')}

You may Authorize to proceed, or Revise the intent to resubmit with different parameters.`,
  },
}

// Basel III Treasury / CAR-Impacting Decision
export const treasuryBaselIII = {
  id: 'treasuryBaselIII',
  label: 'UniCredit Treasury Pilot (Basel III / CAR)',
  domain: 'banking',
  intentFields: [
    { name: 'counterpartyName', label: 'Counterparty Name', type: 'text', required: true },
    { name: 'instrumentType', label: 'Instrument Type', type: 'select', options: ['Loan', 'Bond', 'Derivative', 'Equity'], required: true },
    { name: 'amountEUR', label: 'Amount (EUR)', type: 'number', required: true },
    { name: 'capitalImpact', label: 'Capital Impact', type: 'select', options: ['CAR-Impacting', 'Non-Impacting'], required: true },
  ],
  toolCatalog: [
    { id: 'counterparty_rating', label: 'Counterparty Credit Rating Lookup', toolName: 'credit_rating.lookup', simulateFailure: false },
    { id: 'car_calc', label: 'CAR (Capital Adequacy Ratio) Calculation', toolName: 'basel3.car_calculator', simulateFailure: true },
    { id: 'risk_weighting', label: 'Risk Weight Assignment', toolName: 'basel3.risk_weight', simulateFailure: false },
    { id: 'execute_trade', label: 'Execute Trade', toolName: 'trading.execute', simulateFailure: false },
  ],
  riskRules: [
    {
      id: 'large_amount_threshold',
      test: (fields) => parseInt(fields.amountEUR) > 50000000, // EUR 50M threshold
      classification: 'Basel III / CAR-Impacting Decision',
      citation: `Basel III Capital Requirements Directive (CRD IV/V)
Clause: Transactions exceeding EUR 50M in notional amount require governance review.
All CAR-impacting decisions must be approved by Risk Management and validated by AI governance layer.
Reference: European Banking Authority (EBA) Guidelines on AI Governance, Dec 2023.`,
      severity: 'block',
    },
    {
      id: 'car_impacting_flag',
      test: (fields) => fields.capitalImpact === 'CAR-Impacting',
      classification: 'Basel III / CAR-Impacting Decision',
      citation: `Basel III Capital Requirements Directive (CRD IV/V)
Clause: Capital Adequacy Ratio (CAR) is a core prudential metric.
Any AI decision that affects CAR must undergo pre-execution governance verification.
Minimum CAR requirement: 8% (pillar 1) + macro-prudential buffers.
Reference: Regulation (EU) No 575/2013 (CRR) and Directive 2013/36/EU (CRD IV).`,
      severity: 'block',
    },
  ],
  vetoCopy: {
    title: 'CAR & Risk Governance Gate (Basel III)',
    bodyTemplate: (intent, matchedRules) => `This trading decision triggers ${matchedRules.length} capital-governance gate(s):
${matchedRules.map(r => `  • ${r.classification}`).join('\n')}

Approval confirms Risk Management validation and AI governance verification.
Revision allows parameter adjustment or escalation to human traders.`,
  },
}

const CAPSULES = {
  [hospitalityAnnexIII.id]: hospitalityAnnexIII,
  [treasuryBaselIII.id]: treasuryBaselIII,
}

export function getCapsule(id) {
  return CAPSULES[id]
}
