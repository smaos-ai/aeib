import { useState, useEffect } from 'react'

export default function SideNavigationPanel() {
  const [currentSection, setCurrentSection] = useState(1)
  const [isCompressed, setIsCompressed] = useState(false)
  const [isHovered, setIsHovered] = useState(false)

  const sections = [
    { id: 1, name: 'System Status', icon: '⚡', color: '#3b82f6', brings: 'Real-time metrics & sandbox pool info' },
    { id: 2, name: 'Port Map', icon: '🔍', color: '#3b82f6', brings: 'Service ports, health checks, start/stop' },
    { id: 3, name: 'Architecture', icon: '🏗️', color: '#3b82f6', brings: 'How SMAOS works with real examples' },
    { id: 4, name: 'Compliance', icon: '📋', color: '#a78bfa', brings: 'Regulatory requirements breakdown' },
    { id: 5, name: 'Reports', icon: '📄', color: '#10b981', brings: 'Generate compliance reports for regulators' },
    { id: 6, name: 'Metrics', icon: '📊', color: '#f59e0b', brings: 'Live token speed, memory, CPU grades' },
    { id: 7, name: 'Terminal', icon: '⚙️', color: '#f59e0b', brings: 'Live policy checks & proof ledger stream' },
    { id: 8, name: 'Flows', icon: '🔄', color: '#06b6d4', brings: '4 animated system architecture flows' },
    { id: 9, name: 'Simulator', icon: '💳', color: '#ec4899', brings: 'Interactive hotel booking simulation' },
    { id: 10, name: 'DAG', icon: '🌳', color: '#8b5cf6', brings: 'Step-by-step agent execution flow' },
    { id: 11, name: 'Ledger', icon: '📜', color: '#14b8a6', brings: 'Immutable cryptographic proof trail' }
  ]

  // Detect which section is in view
  useEffect(() => {
    const handleScroll = () => {
      const allSections = document.querySelectorAll('[data-section]')
      let currentSectionId = 1

      allSections.forEach(section => {
        const rect = section.getBoundingClientRect()
        if (rect.top <= 200 && rect.bottom > 200) {
          currentSectionId = parseInt(section.getAttribute('data-section'))
        }
      })

      setCurrentSection(currentSectionId)
      setIsCompressed(window.scrollY > 300)
    }

    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  const handleSectionClick = (id) => {
    const element = document.querySelector(`[data-section="${id}"]`)
    if (element) {
      setIsCompressed(true)
      setTimeout(() => {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 100)
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        right: 0,
        top: isCompressed ? '60px' : '0',
        height: isCompressed ? 'calc(100vh - 60px)' : '100vh',
        width: isCompressed ? '80px' : '100%',
        background: isCompressed
          ? 'linear-gradient(180deg, rgba(10, 14, 39, 0.98) 0%, rgba(10, 14, 39, 0.95) 100%)'
          : 'transparent',
        backdropFilter: isCompressed ? 'blur(12px)' : 'none',
        border: isCompressed ? '2px solid rgba(59, 130, 246, 0.2)' : 'none',
        borderTop: 'none',
        borderRight: 'none',
        zIndex: 50,
        transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column'
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Compressed Mode - Vertical Icon Bar */}
      {isCompressed && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            padding: '12px 8px',
            overflowY: 'auto',
            height: '100%',
            alignItems: 'center'
          }}
        >
          {sections.map((section) => {
            const isCurrent = currentSection === section.id
            return (
              <div key={section.id} style={{ position: 'relative', width: '100%' }}>
                <button
                  onClick={() => handleSectionClick(section.id)}
                  aria-label={section.name}
                  aria-current={isCurrent ? 'page' : undefined}
                  style={{
                    width: '64px',
                    height: '64px',
                    borderRadius: '12px',
                    background: isCurrent
                      ? `linear-gradient(135deg, ${section.color}30 0%, ${section.color}15 100%)`
                      : 'rgba(26, 31, 58, 0.6)',
                    border: `2px solid ${isCurrent ? section.color : 'rgba(100, 116, 139, 0.2)'}`,
                    color: section.color,
                    fontSize: '28px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    transition: 'all 0.3s ease',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: isCurrent ? `0 0 20px ${section.color}40` : 'none',
                    animation: isCurrent ? 'pulse 2s infinite' : 'none',
                    outline: 'none',
                  }}
                  onMouseEnter={(e) => {
                    if (!isCurrent) {
                      e.currentTarget.style.background = `linear-gradient(135deg, ${section.color}20 0%, ${section.color}10 100%)`
                      e.currentTarget.style.borderColor = `${section.color}60`
                      e.currentTarget.style.transform = 'scale(1.05)'
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isCurrent) {
                      e.currentTarget.style.background = 'rgba(26, 31, 58, 0.6)'
                      e.currentTarget.style.borderColor = 'rgba(100, 116, 139, 0.2)'
                      e.currentTarget.style.transform = 'scale(1)'
                    }
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.outline = `2px solid ${section.color}`;
                    e.currentTarget.style.outlineOffset = '2px';
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.outline = 'none';
                  }}
                  title={section.name}
                >
                  <span aria-hidden="true">{section.icon}</span>
                </button>

                {/* Tooltip on hover - with description */}
                {isHovered && (
                  <div
                    style={{
                      position: 'absolute',
                      left: '-250px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: `linear-gradient(135deg, ${section.color}30 0%, ${section.color}12 100%)`,
                      border: `2px solid ${section.color}`,
                      borderRadius: '10px',
                      padding: '10px 14px',
                      fontSize: '10px',
                      fontWeight: 'bold',
                      color: '#e0e0e0',
                      whiteSpace: 'normal',
                      maxWidth: '220px',
                      pointerEvents: 'none',
                      animation: 'slideInRight 0.3s ease',
                      boxShadow: `0 8px 24px ${section.color}30`,
                      backdropFilter: 'blur(8px)'
                    }}
                  >
                    <div style={{ color: section.color, marginBottom: '4px', fontWeight: 'bold' }}>
                      {section.icon} {section.name}
                    </div>
                    <div style={{ color: '#a0a0a0', fontSize: '9px', lineHeight: '1.3' }}>
                      {section.brings}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Expanded Mode - Full Navigation Panel */}
      {!isCompressed && (
        <div
          style={{
            width: '100%',
            height: '100%',
            padding: '0',
            display: 'flex',
            flexDirection: 'column',
            background: 'transparent',
            overflow: 'hidden'
          }}
        >
          {/* Header with collapse hint */}
          <div
            style={{
              padding: '24px',
              background: 'linear-gradient(180deg, rgba(10, 14, 39, 0.95) 0%, rgba(10, 14, 39, 0.85) 100%)',
              borderBottom: '2px solid rgba(59, 130, 246, 0.2)',
              textAlign: 'center'
            }}
          >
            <div
              style={{
                fontSize: '16px',
                fontWeight: 'bold',
                color: '#3b82f6',
                marginBottom: '8px'
              }}
            >
              🧭 Navigate Cockpit
            </div>
            <div
              style={{
                fontSize: '10px',
                color: '#a0a0a0'
              }}
            >
              Scroll down to collapse to right sidebar
            </div>
          </div>

          {/* Sections Grid */}
          <div
            style={{
              flex: 1,
              padding: '20px',
              overflowY: 'auto',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
              gap: '12px'
            }}
          >
            {sections.map((section) => {
              const isCurrent = currentSection === section.id
              return (
                <button
                  key={section.id}
                  onClick={() => handleSectionClick(section.id)}
                  aria-label={section.name}
                  aria-current={isCurrent ? 'page' : undefined}
                  style={{
                    padding: '14px',
                    background: isCurrent
                      ? `linear-gradient(135deg, ${section.color}25 0%, ${section.color}10 100%)`
                      : 'linear-gradient(135deg, rgba(26, 31, 58, 0.8) 0%, rgba(26, 31, 58, 0.6) 100%)',
                    border: `2px solid ${isCurrent ? section.color : 'rgba(100, 116, 139, 0.3)'}`,
                    borderRadius: '10px',
                    color: '#e0e0e0',
                    fontSize: '13px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    gap: '6px',
                    boxShadow: isCurrent ? `0 8px 24px ${section.color}30` : '0 2px 8px rgba(0,0,0,0.2)',
                    transform: isCurrent ? 'scale(1.02)' : 'scale(1)',
                    animation: isCurrent ? 'bounce 0.6s ease' : 'none',
                    outline: 'none',
                  }}
                  onMouseEnter={(e) => {
                    if (!isCurrent) {
                      e.currentTarget.style.background = `linear-gradient(135deg, ${section.color}20 0%, ${section.color}10 100%)`
                      e.currentTarget.style.borderColor = `${section.color}60`
                      e.currentTarget.style.transform = 'translateY(-4px)'
                      e.currentTarget.style.boxShadow = `0 12px 32px ${section.color}25`
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isCurrent) {
                      e.currentTarget.style.background = 'linear-gradient(135deg, rgba(26, 31, 58, 0.8) 0%, rgba(26, 31, 58, 0.6) 100%)'
                      e.currentTarget.style.borderColor = 'rgba(100, 116, 139, 0.3)'
                      e.currentTarget.style.transform = 'scale(1)'
                      e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.2)'
                    }
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.outline = `2px solid ${section.color}`;
                    e.currentTarget.style.outlineOffset = '2px';
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.outline = 'none';
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%' }}>
                    <span aria-hidden="true" style={{ fontSize: '20px' }}>{section.icon}</span>
                    <span style={{ color: isCurrent ? section.color : '#c5c5c5' }}>
                      {section.name}
                    </span>
                  </div>
                  <span style={{
                    fontSize: '9px',
                    color: '#c5c5c5',
                    lineHeight: '1.3',
                    fontWeight: 'normal'
                  }}>
                    → {section.brings}
                  </span>
                </button>
              )
            })}
          </div>

          {/* Footer */}
          <div
            style={{
              padding: '16px',
              background: 'rgba(0, 0, 0, 0.2)',
              borderTop: '1px solid rgba(100, 116, 139, 0.2)',
              fontSize: '9px',
              color: '#4b5563',
              textAlign: 'center',
              lineHeight: '1.4'
            }}
          >
            📍 Current: Section {currentSection}<br/>
            ⬇️ Scroll to collapse navigation
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 20px rgba(59, 130, 246, 0.4); }
          50% { box-shadow: 0 0 30px rgba(59, 130, 246, 0.6); }
        }
        @keyframes bounce {
          0%, 100% { transform: scale(1.02); }
          50% { transform: scale(1.08); }
        }
        @keyframes slideInRight {
          from {
            opacity: 0;
            transform: translateY(-50%) translateX(10px);
          }
          to {
            opacity: 1;
            transform: translateY(-50%) translateX(0);
          }
        }
      `}</style>
    </div>
  )
}
