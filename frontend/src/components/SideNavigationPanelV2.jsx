import { useState, useEffect } from 'react'

export default function SideNavigationPanel() {
  const [currentSection, setCurrentSection] = useState(1)
  const [isCompressed, setIsCompressed] = useState(false)
  const [hoveredId, setHoveredId] = useState(null)

  const sections = [
    { id: 1, name: 'System Status', icon: '⚡', color: '#3b82f6', category: 'Core', brings: 'Real-time metrics & sandbox pool' },
    { id: 2, name: 'Service Ports', icon: '🔍', color: '#3b82f6', category: 'Core', brings: 'Service health & control' },
    { id: 3, name: 'Architecture', icon: '🏗️', color: '#3b82f6', category: 'Learn', brings: 'How SMAOS works' },
    { id: 4, name: 'Compliance', icon: '📋', color: '#a78bfa', category: 'Regulations', brings: 'Regulatory requirements' },
    { id: 5, name: 'Reports', icon: '📄', color: '#10b981', category: 'Compliance', brings: 'Generate reports' },
    { id: '4b', name: 'Evidence', icon: '📊', color: '#06b6d4', category: 'Compliance', brings: 'Track progress' },
    { id: 6, name: 'Metrics', icon: '📈', color: '#f59e0b', category: 'Monitor', brings: 'Live performance' },
    { id: 7, name: 'Terminal', icon: '⚙️', color: '#f59e0b', category: 'Monitor', brings: 'Live execution logs' },
    { id: 8, name: 'Flows', icon: '🔄', color: '#06b6d4', category: 'Visualize', brings: 'Animated architecture' },
    { id: 9, name: 'Simulator', icon: '💳', color: '#ec4899', category: 'Test', brings: 'Interactive demo' },
    { id: 10, name: 'Execution DAG', icon: '🌳', color: '#8b5cf6', category: 'Test', brings: 'Step-by-step flow' },
    { id: 11, name: 'Proof Ledger', icon: '📜', color: '#14b8a6', category: 'Trust', brings: 'Immutable trail' }
  ]

  // Detect which section is in view
  useEffect(() => {
    const handleScroll = () => {
      const allSections = document.querySelectorAll('[data-section]')
      let currentSectionId = 1

      allSections.forEach(section => {
        const rect = section.getBoundingClientRect()
        if (rect.top <= 200 && rect.bottom > 200) {
          currentSectionId = parseInt(section.getAttribute('data-section')) || section.getAttribute('data-section')
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

  // Group sections by category
  const categories = {
    'Core': sections.filter(s => s.category === 'Core'),
    'Learn': sections.filter(s => s.category === 'Learn'),
    'Regulations': sections.filter(s => s.category === 'Regulations'),
    'Compliance': sections.filter(s => s.category === 'Compliance'),
    'Monitor': sections.filter(s => s.category === 'Monitor'),
    'Visualize': sections.filter(s => s.category === 'Visualize'),
    'Test': sections.filter(s => s.category === 'Test'),
    'Trust': sections.filter(s => s.category === 'Trust')
  }

  return (
    <div
      style={{
        position: 'fixed',
        right: 0,
        top: isCompressed ? '60px' : '0',
        height: isCompressed ? 'calc(100vh - 60px)' : '100vh',
        width: isCompressed ? '100px' : '100%',
        background: isCompressed
          ? 'linear-gradient(180deg, rgba(10, 14, 39, 0.98) 0%, rgba(10, 14, 39, 0.95) 100%)'
          : 'transparent',
        backdropFilter: isCompressed ? 'blur(16px)' : 'none',
        border: isCompressed ? '2px solid rgba(59, 130, 246, 0.15)' : 'none',
        borderTop: 'none',
        borderRight: 'none',
        borderLeft: isCompressed ? '2px solid rgba(59, 130, 246, 0.15)' : 'none',
        zIndex: 50,
        transition: 'all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      {/* COMPRESSED MODE - Vertical Icon Bar with Better Spacing */}
      {isCompressed && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            padding: '16px 12px',
            overflowY: 'auto',
            height: '100%',
            alignItems: 'center'
          }}
        >
          {sections.map((section) => {
            const isCurrent = String(currentSection) === String(section.id)
            const isHovered = hoveredId === section.id

            return (
              <div key={section.id} style={{ position: 'relative', width: '100%' }}>
                <button
                  onMouseEnter={() => setHoveredId(section.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  onClick={() => handleSectionClick(section.id)}
                  aria-label={`Navigate to ${section.name}: ${section.brings}`}
                  aria-current={isCurrent ? 'page' : undefined}
                  style={{
                    width: '76px',
                    height: '76px',
                    borderRadius: '14px',
                    background: isCurrent
                      ? `linear-gradient(135deg, ${section.color}35 0%, ${section.color}20 100%)`
                      : isHovered
                      ? `linear-gradient(135deg, ${section.color}25 0%, ${section.color}15 100%)`
                      : 'rgba(30, 41, 59, 0.8)',
                    border: `2px solid ${isCurrent ? section.color : isHovered ? `${section.color}60` : 'rgba(100, 116, 139, 0.2)'}`,
                    color: section.color,
                    fontSize: '32px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    transition: 'all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: isCurrent
                      ? `0 0 20px ${section.color}40, inset 0 0 20px ${section.color}20`
                      : isHovered
                      ? `0 8px 16px ${section.color}20`
                      : '0 2px 8px rgba(0,0,0,0.3)',
                    transform: isCurrent ? 'scale(1.08)' : isHovered ? 'scale(1.05) translateY(-2px)' : 'scale(1)',
                    animation: isCurrent ? 'glow-pulse 2s ease-in-out infinite' : 'none',
                    outline: 'none'
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.outline = `2px solid ${section.color}`
                    e.currentTarget.style.outlineOffset = '2px'
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.outline = 'none'
                  }}
                >
                  {section.icon}
                </button>

                {/* Enhanced Tooltip - Visible on hover */}
                {isHovered && (
                  <div
                    style={{
                      position: 'absolute',
                      left: '-280px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: `linear-gradient(135deg, ${section.color}30 0%, ${section.color}15 100%)`,
                      border: `2px solid ${section.color}`,
                      borderRadius: '12px',
                      padding: '12px 16px',
                      fontSize: '11px',
                      fontWeight: '600',
                      color: '#e0e0e0',
                      whiteSpace: 'normal',
                      maxWidth: '260px',
                      pointerEvents: 'none',
                      animation: 'slideInRight 0.3s ease',
                      boxShadow: `0 12px 32px ${section.color}30, inset 0 0 20px rgba(255,255,255,0.1)`,
                      backdropFilter: 'blur(12px)',
                      zIndex: 100
                    }}
                  >
                    <div style={{ color: section.color, marginBottom: '6px', fontWeight: 'bold', fontSize: '12px' }}>
                      {section.icon} {section.name}
                    </div>
                    <div style={{ color: '#a0a0a0', fontSize: '10px', lineHeight: '1.4' }}>
                      {section.brings}
                    </div>
                    <div style={{ color: '#4b5563', fontSize: '9px', marginTop: '6px', paddingTop: '6px', borderTop: `1px solid ${section.color}40` }}>
                      Category: {section.category}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* EXPANDED MODE - Full Navigation with Categories */}
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
          {/* Header */}
          <div
            style={{
              padding: '32px 28px 24px',
              background: 'linear-gradient(180deg, rgba(10, 14, 39, 0.98) 0%, rgba(10, 14, 39, 0.85) 100%)',
              borderBottom: '2px solid rgba(59, 130, 246, 0.2)',
              textAlign: 'center',
              backdropFilter: 'blur(16px)'
            }}
          >
            <div
              style={{
                fontSize: '18px',
                fontWeight: 'bold',
                color: '#3b82f6',
                marginBottom: '8px'
              }}
            >
              🧭 Navigate
            </div>
            <div
              style={{
                fontSize: '11px',
                color: '#a0a0a0',
                lineHeight: '1.4'
              }}
            >
              Choose a section below
              <br/>
              Scroll down to collapse sidebar
            </div>
          </div>

          {/* Sections - Grouped by Category */}
          <div
            style={{
              flex: 1,
              padding: '20px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px'
            }}
          >
            {Object.entries(categories).map(([category, items]) =>
              items.length > 0 && (
                <div key={category} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {/* Category Header */}
                  <div
                    style={{
                      fontSize: '10px',
                      fontWeight: 'bold',
                      color: '#4b5563',
                      textTransform: 'uppercase',
                      letterSpacing: '1px',
                      paddingLeft: '8px'
                    }}
                  >
                    {category}
                  </div>

                  {/* Buttons in Category */}
                  {items.map((section) => {
                    const isCurrent = String(currentSection) === String(section.id)

                    return (
                      <button
                        key={section.id}
                        onClick={() => handleSectionClick(section.id)}
                        aria-label={`${section.name}: ${section.brings}`}
                        aria-current={isCurrent ? 'page' : undefined}
                        onMouseEnter={() => setHoveredId(section.id)}
                        onMouseLeave={() => setHoveredId(null)}
                        style={{
                          padding: '12px 14px',
                          background: isCurrent
                            ? `linear-gradient(135deg, ${section.color}30 0%, ${section.color}12 100%)`
                            : hoveredId === section.id
                            ? `linear-gradient(135deg, ${section.color}20 0%, ${section.color}08 100%)`
                            : 'rgba(30, 41, 59, 0.5)',
                          border: `2px solid ${isCurrent ? section.color : hoveredId === section.id ? `${section.color}60` : 'rgba(100, 116, 139, 0.2)'}`,
                          borderRadius: '10px',
                          color: '#e0e0e0',
                          fontSize: '13px',
                          fontWeight: '600',
                          cursor: 'pointer',
                          transition: 'all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '12px',
                          boxShadow: isCurrent
                            ? `0 8px 24px ${section.color}25, inset 0 0 12px ${section.color}15`
                            : hoveredId === section.id
                            ? `0 6px 16px ${section.color}15`
                            : '0 2px 6px rgba(0,0,0,0.2)',
                          transform: isCurrent ? 'scale(1.01)' : hoveredId === section.id ? 'translateY(-2px)' : 'scale(1)',
                          animation: isCurrent ? 'glow-pulse 2s ease-in-out infinite' : 'none',
                          outline: 'none'
                        }}
                        onFocus={(e) => {
                          e.currentTarget.style.outline = `2px solid ${section.color}`
                          e.currentTarget.style.outlineOffset = '2px'
                        }}
                        onBlur={(e) => {
                          e.currentTarget.style.outline = 'none'
                        }}
                      >
                        <span style={{ fontSize: '18px', flexShrink: 0 }}>{section.icon}</span>
                        <div style={{ flex: 1, textAlign: 'left' }}>
                          <div style={{ color: isCurrent ? section.color : '#e0e0e0', marginBottom: '2px' }}>
                            {section.name}
                          </div>
                          <div style={{ fontSize: '10px', color: '#a0a0a0', lineHeight: '1.2' }}>
                            → {section.brings}
                          </div>
                        </div>
                        {isCurrent && <span style={{ color: section.color, fontSize: '12px' }}>●</span>}
                      </button>
                    )
                  })}
                </div>
              )
            )}
          </div>

          {/* Footer */}
          <div
            style={{
              padding: '14px 20px',
              background: 'rgba(0, 0, 0, 0.2)',
              borderTop: '1px solid rgba(100, 116, 139, 0.2)',
              fontSize: '9px',
              color: '#4b5563',
              textAlign: 'center',
              lineHeight: '1.4'
            }}
          >
            📍 Current: {currentSection}
            <br/>
            ⬇️ Scroll to collapse
          </div>
        </div>
      )}

      <style>{`
        @keyframes glow-pulse {
          0%, 100% { box-shadow: 0 0 20px rgba(59, 130, 246, 0.4), inset 0 0 20px rgba(59, 130, 246, 0.2); }
          50% { box-shadow: 0 0 30px rgba(59, 130, 246, 0.6), inset 0 0 20px rgba(59, 130, 246, 0.3); }
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
