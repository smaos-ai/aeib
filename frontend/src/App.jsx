import React, { useState } from 'react'
import { Navbar, NavbarGroup, NavbarHeading } from '@blueprintjs/core'
import '@blueprintjs/core/lib/css/blueprint.css'
import '@blueprintjs/icons/lib/css/blueprint-icons.css'
import './blueprint-theme.css'

import LandingPage from './components/LandingPage'
import OnboardingModal from './components/OnboardingModal'
import LeftIntentPane from './components/panes/LeftIntentPane'
import CenterWorkPane from './components/panes/CenterWorkPane'
import RightInspectorPane from './components/panes/RightInspectorPane'
import { GovernanceProvider } from './state/GovernanceContext'

function App() {
  const [showLandingPage, setShowLandingPage] = useState(() => {
    return false
  })

  const [showOnboarding, setShowOnboarding] = useState(false)

  const handleEnterDashboard = () => {
    setShowLandingPage(false)
    localStorage.setItem('smaos-visited', 'true')
  }

  const handleOnboardingClose = () => {
    setShowOnboarding(false)
    localStorage.setItem('smaos-onboarded', 'true')
  }

  if (showLandingPage) {
    return <LandingPage onEnterDashboard={handleEnterDashboard} />
  }

  return (
    <GovernanceProvider>
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#fafafa' }}>
        {showOnboarding && <OnboardingModal onClose={handleOnboardingClose} />}

        {/* Top Nav */}
        <Navbar style={{ background: '#ffffff', borderBottom: '1px solid #cccccc' }}>
          <NavbarGroup align="left">
            <NavbarHeading style={{ fontSize: '18px', fontWeight: '700', color: '#000000' }}>
              🛡️ SMAOS Governance Cockpit (3-Pane Agentic UI)
            </NavbarHeading>
          </NavbarGroup>
        </Navbar>

        {/* 3-Pane Layout: Left (intent) | Center (execution) | Right (inspector) */}
        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '320px minmax(600px, 1fr) 380px', gap: '0', overflow: 'hidden', background: '#fafafa' }}>
          {/* LEFT PANE: Intent + Risk Classification */}
          <div style={{ borderRight: '1px solid #cccccc', overflowY: 'auto', background: '#ffffff' }}>
            <ErrorBoundary>
              <LeftIntentPane />
            </ErrorBoundary>
          </div>

          {/* CENTER PANE: Work Surface (Diamond Topology) */}
          <div style={{ borderRight: '1px solid #cccccc', overflowY: 'auto', background: '#fafafa' }}>
            <ErrorBoundary>
              <CenterWorkPane />
            </ErrorBoundary>
          </div>

          {/* RIGHT PANE: Inspector (Proof Ledger + Board Dashboard) */}
          <div style={{ overflowY: 'auto', background: '#ffffff' }}>
            <ErrorBoundary>
              <RightInspectorPane />
            </ErrorBoundary>
          </div>
        </div>
      </div>
    </GovernanceProvider>
  )
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', color: '#dd0000', background: '#fff0f0', fontFamily: 'monospace', fontSize: '12px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          <strong>🔴 COMPONENT ERROR</strong>
          {'\n\n'}
          {this.state.error?.toString()}
        </div>
      )
    }
    return this.props.children
  }
}

export default App
