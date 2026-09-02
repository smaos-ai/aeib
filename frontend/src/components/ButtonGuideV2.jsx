import { useState } from 'react'
import { BUTTON_SCHEMAS } from './ButtonDescriptions'

export default function ButtonGuide() {
  const [selectedCategory, setSelectedCategory] = useState('system-status')
  const [selectedButton, setSelectedButton] = useState('check-status')
  const [expandedSection, setExpandedSection] = useState('description')

  // Group buttons by dashboard section
  const categories = {
    'system-status': {
      name: 'System Status & Ports',
      icon: '⚡',
      color: '#3b82f6',
      description: 'Monitor and control services',
      buttons: ['check-status', 'start-service', 'stop-service', 'copy-url', 'open-browser']
    },
    'transaction': {
      name: 'Transaction Simulator',
      icon: '💳',
      color: '#ec4899',
      description: '8-step booking demo',
      buttons: ['start-simulation']
    },
    'dag': {
      name: 'Agent Execution DAG',
      icon: '🌳',
      color: '#8b5cf6',
      description: 'Step-by-step flow navigation',
      buttons: ['pause-resume', 'previous-next-step', 'set-speed']
    },
    'compliance': {
      name: 'Compliance Reports',
      icon: '📄',
      color: '#10b981',
      description: 'Generate and download PDFs',
      buttons: ['generate-report', 'download-pdf']
    }
  }

  const currentCategory = categories[selectedCategory]
  const button = BUTTON_SCHEMAS[selectedButton]

  if (!button || !currentCategory) return null

  const categoryButtons = currentCategory.buttons.map(key => BUTTON_SCHEMAS[key]).filter(Boolean)

  return (
    <div style={{ padding: '0' }}>
      {/* Header */}
      <div style={{
        fontSize: '12px',
        fontWeight: 'bold',
        color: '#3b82f6',
        marginBottom: '14px',
        textTransform: 'uppercase',
        letterSpacing: '1px'
      }}>
        📚 Button Reference Guide (by Dashboard)
      </div>

      {/* Info Box */}
      <div style={{
        background: 'rgba(16, 185, 129, 0.1)',
        border: '1px solid rgba(16, 185, 129, 0.3)',
        borderRadius: '8px',
        padding: '12px',
        marginBottom: '16px',
        fontSize: '10px',
        color: '#a0a0a0'
      }}>
        💡 <strong>How to use:</strong> Select a dashboard section on the left, then choose a button to see INPUT, PROCESS, OUTPUT, and EXAMPLE. Small ⓘ icons on buttons show this info.
      </div>

      {/* Two-Column Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: '16px' }}>
        {/* LEFT: Category Selection */}
        <div style={{
          background: 'rgba(26, 31, 58, 0.6)',
          border: '1px solid rgba(100, 116, 139, 0.3)',
          borderRadius: '10px',
          padding: '12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          height: 'fit-content'
        }}>
          <div style={{
            fontSize: '10px',
            fontWeight: 'bold',
            color: '#a0a0a0',
            textTransform: 'uppercase',
            marginBottom: '4px'
          }}>
            Dashboards
          </div>

          {Object.entries(categories).map(([key, cat]) => (
            <button
              key={key}
              onClick={() => {
                setSelectedCategory(key)
                setSelectedButton(cat.buttons[0])
              }}
              style={{
                padding: '10px',
                background: selectedCategory === key
                  ? `linear-gradient(135deg, ${cat.color}30 0%, ${cat.color}15 100%)`
                  : 'rgba(30, 41, 59, 0.5)',
                border: selectedCategory === key ? `2px solid ${cat.color}` : '1px solid rgba(100, 116, 139, 0.2)',
                borderRadius: '8px',
                color: selectedCategory === key ? cat.color : '#a0a0a0',
                fontSize: '10px',
                fontWeight: 'bold',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                textAlign: 'left',
                display: 'flex',
                flexDirection: 'column',
                gap: '2px'
              }}
            >
              <div>{cat.icon} {cat.name}</div>
              <div style={{ fontSize: '8px', opacity: 0.7 }}>{cat.buttons.length} buttons</div>
            </button>
          ))}
        </div>

        {/* RIGHT: Button Details */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}>
          {/* Category Header */}
          <div style={{
            background: `linear-gradient(135deg, ${currentCategory.color}15 0%, ${currentCategory.color}05 100%)`,
            border: `2px solid ${currentCategory.color}`,
            borderRadius: '10px',
            padding: '12px',
            backdropFilter: 'blur(8px)'
          }}>
            <div style={{
              fontSize: '12px',
              fontWeight: 'bold',
              color: currentCategory.color,
              marginBottom: '4px'
            }}>
              {currentCategory.icon} {currentCategory.name}
            </div>
            <div style={{
              fontSize: '10px',
              color: '#a0a0a0'
            }}>
              {currentCategory.description}
            </div>
          </div>

          {/* Button Selection Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(90px, 1fr))',
            gap: '8px'
          }}>
            {categoryButtons.map((btn) => (
              <button
                key={btn.name}
                onClick={() => setSelectedButton(Object.keys(BUTTON_SCHEMAS).find(k => BUTTON_SCHEMAS[k] === btn))}
                title={`${btn.icon} ${btn.name}: ${btn.description}`}
                style={{
                  padding: '12px 8px',
                  background: selectedButton === Object.keys(BUTTON_SCHEMAS).find(k => BUTTON_SCHEMAS[k] === btn)
                    ? `linear-gradient(135deg, ${btn.name ? '#3b82f6' : '#a0a0a0'}20 0%, ${btn.name ? '#3b82f6' : '#a0a0a0'}10 100%)`
                    : 'rgba(30, 41, 59, 0.6)',
                  border: selectedButton === Object.keys(BUTTON_SCHEMAS).find(k => BUTTON_SCHEMAS[k] === btn)
                    ? '2px solid #3b82f6'
                    : '1px solid rgba(100, 116, 139, 0.2)',
                  borderRadius: '8px',
                  color: '#a0a0a0',
                  fontSize: '9px',
                  fontWeight: 'bold',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '4px',
                  position: 'relative'
                }}
              >
                <span style={{ fontSize: '16px' }}>{btn.icon}</span>
                <span style={{ textAlign: 'center', lineHeight: '1.2' }}>{btn.name.split(' ').join('\n')}</span>
                {/* Small Info Badge */}
                <div style={{
                  position: 'absolute',
                  top: '-6px',
                  right: '-6px',
                  width: '18px',
                  height: '18px',
                  borderRadius: '50%',
                  background: '#3b82f6',
                  color: 'white',
                  fontSize: '10px',
                  fontWeight: 'bold',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'help',
                  boxShadow: '0 2px 8px rgba(59, 130, 246, 0.4)'
                }}>
                  ⓘ
                </div>
              </button>
            ))}
          </div>

          {/* Button Details Panels */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {/* Title & Description */}
            <div style={{
              background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%)',
              border: '2px solid rgba(59, 130, 246, 0.2)',
              borderRadius: '10px',
              padding: '12px',
              backdropFilter: 'blur(8px)'
            }}>
              <div style={{
                fontSize: '13px',
                fontWeight: 'bold',
                color: '#3b82f6',
                marginBottom: '6px'
              }}>
                {button.icon} {button.name}
              </div>
              <div style={{
                fontSize: '10px',
                color: '#a0a0a0'
              }}>
                {button.description}
              </div>
            </div>

            {/* Accordion Panels */}
            {/* INPUT */}
            <div style={{
              background: 'rgba(30, 41, 59, 0.8)',
              border: '1px solid rgba(100, 116, 139, 0.3)',
              borderRadius: '8px',
              overflow: 'hidden'
            }}>
              <button
                onClick={() => setExpandedSection(expandedSection === 'input' ? null : 'input')}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  background: 'transparent',
                  border: 'none',
                  color: '#a0a0a0',
                  fontSize: '10px',
                  fontWeight: 'bold',
                  textAlign: 'left',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
              >
                <span>📥 INPUT: What data do you provide?</span>
                <span>{expandedSection === 'input' ? '▼' : '▶'}</span>
              </button>
              {expandedSection === 'input' && (
                <div style={{
                  padding: '10px 12px',
                  borderTop: '1px solid rgba(100, 116, 139, 0.2)',
                  fontSize: '9px',
                  color: '#a0a0a0',
                  fontFamily: 'monospace',
                  lineHeight: '1.5'
                }}>
                  {Object.entries(button.input).map(([key, value]) => (
                    <div key={key} style={{ marginBottom: '4px' }}>
                      <span style={{ color: '#3b82f6', fontWeight: 'bold' }}>{key}</span>
                      <span style={{ color: '#a0a0a0' }}>: {value}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* PROCESS */}
            <div style={{
              background: 'rgba(30, 41, 59, 0.8)',
              border: '1px solid rgba(100, 116, 139, 0.3)',
              borderRadius: '8px',
              overflow: 'hidden'
            }}>
              <button
                onClick={() => setExpandedSection(expandedSection === 'process' ? null : 'process')}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  background: 'transparent',
                  border: 'none',
                  color: '#a0a0a0',
                  fontSize: '10px',
                  fontWeight: 'bold',
                  textAlign: 'left',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
              >
                <span>⚙️ PROCESS: What happens?</span>
                <span>{expandedSection === 'process' ? '▼' : '▶'}</span>
              </button>
              {expandedSection === 'process' && (
                <div style={{
                  padding: '10px 12px',
                  borderTop: '1px solid rgba(100, 116, 139, 0.2)',
                  fontSize: '9px',
                  color: '#a0a0a0',
                  lineHeight: '1.6'
                }}>
                  {button.process.map((step, i) => (
                    <div key={i} style={{ marginBottom: '4px' }}>
                      {step}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* OUTPUT */}
            <div style={{
              background: 'rgba(30, 41, 59, 0.8)',
              border: '1px solid rgba(100, 116, 139, 0.3)',
              borderRadius: '8px',
              overflow: 'hidden'
            }}>
              <button
                onClick={() => setExpandedSection(expandedSection === 'output' ? null : 'output')}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  background: 'transparent',
                  border: 'none',
                  color: '#a0a0a0',
                  fontSize: '10px',
                  fontWeight: 'bold',
                  textAlign: 'left',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
              >
                <span>📤 OUTPUT: What result do you get?</span>
                <span>{expandedSection === 'output' ? '▼' : '▶'}</span>
              </button>
              {expandedSection === 'output' && (
                <div style={{
                  padding: '10px 12px',
                  borderTop: '1px solid rgba(100, 116, 139, 0.2)',
                  fontSize: '9px',
                  color: '#a0a0a0',
                  fontFamily: 'monospace',
                  lineHeight: '1.5'
                }}>
                  {Object.entries(button.output).map(([key, value]) => (
                    <div key={key} style={{ marginBottom: '4px' }}>
                      <span style={{ color: '#10b981', fontWeight: 'bold' }}>{key}</span>
                      <span style={{ color: '#a0a0a0' }}>: {value}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* EXAMPLE */}
            <div style={{
              background: 'rgba(30, 41, 59, 0.8)',
              border: '1px solid rgba(100, 116, 139, 0.3)',
              borderRadius: '8px',
              overflow: 'hidden'
            }}>
              <button
                onClick={() => setExpandedSection(expandedSection === 'example' ? null : 'example')}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  background: 'transparent',
                  border: 'none',
                  color: '#a0a0a0',
                  fontSize: '10px',
                  fontWeight: 'bold',
                  textAlign: 'left',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
              >
                <span>💡 EXAMPLE: Real-world usage</span>
                <span>{expandedSection === 'example' ? '▼' : '▶'}</span>
              </button>
              {expandedSection === 'example' && (
                <div style={{
                  padding: '10px 12px',
                  borderTop: '1px solid rgba(100, 116, 139, 0.2)',
                  fontSize: '8px',
                  color: '#a0a0a0',
                  fontFamily: 'monospace',
                  lineHeight: '1.4',
                  maxHeight: '300px',
                  overflow: 'auto'
                }}>
                  <div style={{ color: '#3b82f6', fontWeight: 'bold', marginBottom: '6px' }}>INPUT:</div>
                  <pre style={{ margin: '0 0 12px 0', color: '#a0a0a0', whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify(button.example.input, null, 2)}
                  </pre>

                  <div style={{ color: '#10b981', fontWeight: 'bold', marginBottom: '6px' }}>OUTPUT:</div>
                  <pre style={{ margin: '0', color: '#a0a0a0', whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify(button.example.output, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
