import { describe, it, expect } from 'vitest'
import { classifyIntent } from '../lib/riskClassifier'
import { CAPSULES } from '../lib/capsules'

describe('Risk Classifier - Treasury', () => {
  const cap = CAPSULES.treasuryBaselIII

  it('HIGH-RISK for €50M CAR trade', () => {
    const r = classifyIntent(cap, {
      counterparty: 'Goldman',
      amount_eur: '50000000',
      instrument: 'Bond',
      capital_impact: 'CAR-Impacting',
    })
    expect(r.highestSeverity).toBe('block')
    expect(r.matchedRules.length).toBeGreaterThan(0)
  })

  it('APPROVED for non-CAR trade', () => {
    const r = classifyIntent(cap, {
      counterparty: 'Bank',
      amount_eur: '100000',
      instrument: 'Equity',
      capital_impact: 'Non-Impacting',
    })
    expect(r.highestSeverity).not.toBe('block')
  })
})

describe('Risk Classifier - Hotel', () => {
  const cap = CAPSULES.hospitalityAnnexIII

  it('HIGH-RISK for PII + credit', () => {
    const r = classifyIntent(cap, {
      guest_name: 'John',
      data_category: 'Credit Score',
      purpose: 'Assessment',
    })
    expect(r.highestSeverity).toBe('block')
  })
})
