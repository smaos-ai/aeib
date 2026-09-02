/**
 * Pure, deterministic risk classification function.
 * No randomness, no side effects — completely unit-testable.
 */
export function classifyIntent(capsule, fields) {
  if (!capsule || !capsule.riskRules) {
    return { matchedRules: [], highestSeverity: 'none', badgeLabel: 'No Rules Configured' }
  }

  const matchedRules = capsule.riskRules.filter(rule => rule.test(fields))

  const severityOrder = { none: 0, warn: 1, block: 2 }
  const highestSeverity = matchedRules.length === 0
    ? 'none'
    : matchedRules.reduce((max, rule) =>
      severityOrder[rule.severity] > severityOrder[max] ? rule.severity : max,
      'none'
    )

  let badgeLabel = 'Approved'
  if (highestSeverity === 'block') {
    badgeLabel = matchedRules[0]?.classification || 'High Risk'
  } else if (highestSeverity === 'warn') {
    badgeLabel = matchedRules[0]?.classification || 'Warning'
  }

  return {
    intentId: fields._id || `intent-${Date.now()}`,
    capsuleId: capsule.id,
    matchedRules,
    highestSeverity,
    badgeLabel,
  }
}
