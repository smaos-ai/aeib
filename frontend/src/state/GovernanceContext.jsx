import React, { createContext, useReducer, useCallback } from 'react'

export const GovernanceContext = createContext(null)
export const GovernanceDispatchContext = createContext(null)

const initialState = {
  capsuleId: 'hospitalityAnnexIII',
  intents: [],
  classifications: [],
  graphState: { nodes: [], edges: [] },
  receipts: [],
  sessionStats: { exposure: 0, risk: 0, controls: 0, exceptions: 0, incidents: 0, regulatoryExposure: [], decisions: { authorized: 0, revised: 0 }, driftFlag: false },
  killSwitchEngaged: false,
  poolStatus: null,
  currentIntentId: null,
  resolvedIntentId: null,
}

function governanceReducer(state, action) {
  switch (action.type) {
    case 'SET_CAPSULE':
      return { ...state, capsuleId: action.payload, intents: [], classifications: [], receipts: [], sessionStats: initialState.sessionStats }

    case 'SUBMIT_INTENT':
      const newIntent = { id: action.payload.id, capsuleId: state.capsuleId, fields: action.payload.fields, submittedAt: new Date() }
      return { ...state, intents: [...state.intents, newIntent], currentIntentId: newIntent.id }

    case 'CLASSIFY_INTENT':
      const newClassification = { ...action.payload, computedAt: new Date() }
      const classifications = state.classifications.filter(c => c.intentId !== action.payload.intentId)
      return { ...state, classifications: [...classifications, newClassification] }

    case 'BUILD_GRAPH':
      return { ...state, graphState: action.payload }

    case 'UPDATE_NODE_STATUS':
      const updatedNodes = state.graphState.nodes.map(n =>
        n.id === action.payload.nodeId ? { ...n, status: action.payload.status } : n
      )
      return { ...state, graphState: { ...state.graphState, nodes: updatedNodes } }

    case 'ADD_RECEIPT':
      return { ...state, receipts: [...state.receipts, action.payload] }

    case 'ENGAGE_KILL_SWITCH':
      const haltedNodes = state.graphState.nodes.map(n =>
        (n.status === 'running' || n.status === 'pending') ? { ...n, status: 'halted' } : n
      )
      return { ...state, killSwitchEngaged: true, graphState: { ...state.graphState, nodes: haltedNodes } }

    case 'RESET_EXECUTION':
      return { ...initialState, capsuleId: state.capsuleId }

    case 'UPDATE_SESSION_STATS':
      return { ...state, sessionStats: action.payload }

    case 'SET_POOL_STATUS':
      return { ...state, poolStatus: action.payload }

    case 'RESOLVE_INTENT':
      return { ...state, resolvedIntentId: action.payload }

    default:
      return state
  }
}

export function GovernanceProvider({ children }) {
  const [state, dispatch] = useReducer(governanceReducer, initialState)

  const actions = {
    setCapsule: useCallback((capsuleId) => dispatch({ type: 'SET_CAPSULE', payload: capsuleId }), []),
    submitIntent: useCallback((id, fields) => dispatch({ type: 'SUBMIT_INTENT', payload: { id, fields } }), []),
    classifyIntent: useCallback((classification) => dispatch({ type: 'CLASSIFY_INTENT', payload: classification }), []),
    buildGraph: useCallback((graph) => dispatch({ type: 'BUILD_GRAPH', payload: graph }), []),
    updateNodeStatus: useCallback((nodeId, status) => dispatch({ type: 'UPDATE_NODE_STATUS', payload: { nodeId, status } }), []),
    addReceipt: useCallback((receipt) => dispatch({ type: 'ADD_RECEIPT', payload: receipt }), []),
    engageKillSwitch: useCallback(() => dispatch({ type: 'ENGAGE_KILL_SWITCH' }), []),
    resetExecution: useCallback(() => dispatch({ type: 'RESET_EXECUTION' }), []),
    updateSessionStats: useCallback((stats) => dispatch({ type: 'UPDATE_SESSION_STATS', payload: stats }), []),
    setPoolStatus: useCallback((poolStatus) => dispatch({ type: 'SET_POOL_STATUS', payload: poolStatus }), []),
    resolveIntent: useCallback((intentId) => dispatch({ type: 'RESOLVE_INTENT', payload: intentId }), []),
  }

  return (
    <GovernanceContext.Provider value={state}>
      <GovernanceDispatchContext.Provider value={actions}>
        {children}
      </GovernanceDispatchContext.Provider>
    </GovernanceContext.Provider>
  )
}

export function useGovernance() {
  const state = React.useContext(GovernanceContext)
  const actions = React.useContext(GovernanceDispatchContext)
  if (!state || !actions) throw new Error('useGovernance must be used inside GovernanceProvider')
  return { state, ...actions }
}
