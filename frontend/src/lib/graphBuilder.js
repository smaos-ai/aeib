/**
 * Build a diamond-topology DAG for the work surface.
 * intent (top) → N parallel tools (middle) → converge (bottom)
 * One tool is marked simulateFailure: true and spawns a retry branch.
 */

export function buildDiamondGraph(capsule, intent, classification) {
  const nodes = []
  const edges = []

  // Rank 0: Intent node (top, centered)
  const intentNode = {
    id: 'node-intent',
    kind: 'intent',
    label: `Intent: ${classification.badgeLabel}`,
    status: 'pending',
    data: { classification },
    position: { x: 250, y: 20 },
  }
  nodes.push(intentNode)

  // Rank 1: Tool nodes (parallel, spread vertically)
  const tools = capsule.toolCatalog || []
  const toolNodeHeight = 120
  const toolNodeSpacing = 140
  const toolStartY = 120

  tools.forEach((tool, i) => {
    const hasRiskFlag = classification.highestSeverity === 'block' && i === 0 // First tool gets the risk flag
    const isGateNode = hasRiskFlag && classification.highestSeverity === 'block'

    const toolNode = {
      id: `node-tool-${i}`,
      kind: isGateNode ? 'gate' : 'tool',
      label: isGateNode ? `Authorization Gate: ${tool.label}` : tool.label,
      toolName: tool.toolName,
      status: isGateNode ? 'blocked' : 'pending',
      parentIds: ['node-intent'],
      simulateFailure: tool.simulateFailure || false,
      riskFlag: hasRiskFlag,
      position: { x: 50 + i * toolNodeSpacing, y: toolStartY },
      data: {
        toolIndex: i,
        tool,
        classification: isGateNode ? classification : undefined,
        nodeId: `node-tool-${i}`,
      },
    }
    nodes.push(toolNode)

    // Edge from intent to tool
    edges.push({
      id: `edge-intent-tool-${i}`,
      source: 'node-intent',
      target: `node-tool-${i}`,
    })

    // If this tool simulates failure, spawn a retry node
    if (tool.simulateFailure) {
      const retryNode = {
        id: `node-retry-${i}`,
        kind: 'retry',
        label: `Retry: ${tool.label}`,
        status: 'pending',
        parentIds: [`node-tool-${i}`],
        position: { x: 50 + i * toolNodeSpacing, y: toolStartY + 120 },
        data: { retryFor: i },
      }
      nodes.push(retryNode)

      // Edge from tool to retry (dashed, shown only when tool fails)
      edges.push({
        id: `edge-tool-retry-${i}`,
        source: `node-tool-${i}`,
        target: `node-retry-${i}`,
        animated: false,
        style: { strokeDasharray: '5,5' },
      })
    }
  })

  // Rank 2: Converge node (bottom, centered)
  const convergeNode = {
    id: 'node-converge',
    kind: 'converge',
    label: 'Results Converged',
    status: 'pending',
    parentIds: tools.map((_, i) => `node-tool-${i}`),
    position: { x: 250, y: 320 },
  }
  nodes.push(convergeNode)

  // Edges from tools to converge
  tools.forEach((_, i) => {
    const source = tools[i].simulateFailure ? `node-retry-${i}` : `node-tool-${i}`
    edges.push({
      id: `edge-tool-converge-${i}`,
      source,
      target: 'node-converge',
    })
  })

  return { nodes, edges }
}
