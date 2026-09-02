/**
 * Compute the 7-tile board dashboard stats from real governance state.
 * All derived from reducer state, never random.
 */

export function computeSessionStats(state) {
  const intents = state.intents || []
  const classifications = state.classifications || []
  const receipts = state.receipts || []
  const nodes = state.graphState?.nodes || []

  // EXPOSURE: count of intents, sum of treasury amounts
  const exposure = intents.length
  const treasuryAmounts = intents
    .map(intent => {
      const f = intent.fields || {}
      return state.capsuleId === 'treasuryBaselIII' ? parseInt(f.amountEUR) || 0 : 0
    })
    .reduce((a, b) => a + b, 0)
  const exposureLabel = state.capsuleId === 'treasuryBaselIII'
    ? `€${(treasuryAmounts / 1000000).toFixed(1)}M`
    : `${exposure} intents`

  // RISK: highest severity reached, count of block-severity rules matched
  const highestSeverity = classifications.length > 0
    ? classifications.reduce((max, c) => {
      const order = { none: 0, warn: 1, block: 2 }
      return order[c.highestSeverity] > order[max] ? c.highestSeverity : max
    }, 'none')
    : 'none'
  const blockRuleCount = classifications.reduce((sum, c) => sum + (c.matchedRules?.filter(r => r.severity === 'block').length || 0), 0)
  const riskLabel = highestSeverity === 'block' ? `${blockRuleCount} block rules` : 'No high-risk'

  // CONTROLS: tool nodes that reached success
  const successToolCount = nodes.filter(n => n.kind === 'tool' && n.status === 'success').length

  // EXCEPTIONS: veto gates triggered (count of classifications with block-severity rules)
  const exceptionsCount = classifications.filter(c => c.highestSeverity === 'block').length

  // INCIDENTS: kill-switch engagements + retry/failure nodes
  const killSwitchEngagements = state.killSwitchEngaged ? 1 : 0
  const retryNodeCount = nodes.filter(n => n.kind === 'retry').length
  const failedNodeCount = nodes.filter(n => (n.status === 'failed' || n.status === 'halted')).length
  const incidentsCount = killSwitchEngagements + retryNodeCount + failedNodeCount

  // REGULATORY EXPOSURE: distinct citations matched across all classifications
  const citationSet = new Set()
  classifications.forEach(c => {
    (c.matchedRules || []).forEach(rule => {
      if (rule.citation) citationSet.add(rule.classification)
    })
  })
  const regulatoryExposure = Array.from(citationSet)

  // DECISIONS: authorized vs revised veto resolutions
  const authorizedCount = receipts.filter(r => r.action === 'veto.authorize').length
  const revisedCount = receipts.filter(r => r.action === 'veto.revise').length
  const decisionsRatio = authorizedCount + revisedCount > 0
    ? `${authorizedCount} authorized / ${revisedCount} revised`
    : 'No veto decisions yet'

  // DRIFT: vetoTriggers / actions ratio vs baseline
  const driftBaseline = 0.2 // If > 20% of actions trigger vetos, flag drift
  const minSampleSize = 3 // Need at least 3 actions to assess drift
  const totalActions = intents.length
  const vetoTriggeredActions = classifications.filter(c => c.highestSeverity === 'block').length
  const driftRate = totalActions >= minSampleSize ? vetoTriggeredActions / totalActions : 0
  const driftFlag = totalActions >= minSampleSize && driftRate > driftBaseline

  return {
    exposure: exposureLabel,
    exposureCount: exposure,
    risk: riskLabel,
    riskSeverity: highestSeverity,
    controls: `${successToolCount} completed`,
    controlsCount: successToolCount,
    exceptions: `${exceptionsCount} triggered`,
    exceptionsCount,
    incidents: `${incidentsCount} events`,
    incidentsCount,
    regulatoryExposure,
    regulatoryExposureLabel: `${citationSet.size} citations`,
    decisions: decisionsRatio,
    decidedCount: authorizedCount + revisedCount,
    authorizedCount,
    revisedCount,
    driftFlag,
    driftRate: (driftRate * 100).toFixed(1),
  }
}
