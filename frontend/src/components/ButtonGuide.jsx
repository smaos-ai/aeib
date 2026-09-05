import { useState } from 'react'
import { BUTTON_SCHEMAS } from './ButtonDescriptions'

export default function ButtonGuide() {
  const [selectedButton, setSelectedButton] = useState('check-status')
  const [expandedSection, setExpandedSection] = useState('description')

  const button = BUTTON_SCHEMAS[selectedButton]
  if (!button) return null

  const buttons = Object.entries(BUTTON_SCHEMAS)

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
        📚 Button Reference Guide
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
        💡 Click any button below to see what it does, what data it needs (INPUT), and what result it produces (OUTPUT).
      </div>

      {/* Button Selection Tabs */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
        gap: '8px',
        marginBottom: '16px'
      }}>
        {buttons.map(([key, btn]) => (
          <button
            key={key}
            onClick={() => setSelectedButton(key)}
            style={{
              padding: '10px',
              background: selectedButton === key
                ? 'linear-gradient(135deg, rgba(59, 130, 246, 0.3) 0%, rgba(59, 130, 246, 0.15) 100%)'
                : 'rgba(26, 31, 58, 0.6)',
              border: selectedButton === key ? '2px solid #3b82f6' : '1px solid rgba(100, 116, 139, 0.2)',
              borderRadius: '8px',
              color: selectedButton === key ? '#3b82f6' : '#a0a0a0',
              fontSize: '10px',
              fontWeight: 'bold',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              textAlign: 'center'
            }}
            onMouseEnter={(e) => {
              if (selectedButton !== key) {
                e.currentTarget.style.background = 'linear-gradient(135deg, rgba(59, 130, 246, 0.2) 0%, rgba(59, 130, 246, 0.1) 100%)'
              }
            }}
            onMouseLeave={(e) => {
              if (selectedButton !== key) {
                e.currentTarget.style.background = 'rgba(26, 31, 58, 0.6)'
              }
            }}
          >
            <div style={{ fontSize: '12px', marginBottom: '2px' }}>{btn.icon}</div>
            {btn.name}
          </button>
        ))}
      </div>

      {/* Selected Button Details */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%)',
        border: '2px solid rgba(59, 130, 246, 0.2)',
        borderRadius: '12px',
        padding: '16px',
        backdropFilter: 'blur(8px)'
      }}>
        {/* Title */}
        <div style={{
          fontSize: '14px',
          fontWeight: 'bold',
          color: '#3b82f6',
          marginBottom: '8px'
        }}>
          {button.icon} {button.name}
        </div>

        {/* Description */}
        <div style={{
          fontSize: '10px',
          color: '#a0a0a0',
          marginBottom: '12px',
          lineHeight: '1.5'
        }}>
          {button.description}
        </div>

        {/* Accordion Sections */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {/* INPUT */}
          <div style={{
            background: 'rgba(30, 41, 59, 0.8)',
            border: '1px solid rgba(100, 116, 139, 0.3)',
            borderRadius: '8px',
            padding: '0'
          }}>
            <button
              onClick={() => setExpandedSection(expandedSection === 'input' ? null : 'input')}
              style={{
                width: '100%',
                padding: '10px 12px',
                background: 'transparent',
                border: 'none',
                color: '#a0a0a0',
                fontSize: '11px',
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
            padding: '0'
          }}>
            <button
              onClick={() => setExpandedSection(expandedSection === 'process' ? null : 'process')}
              style={{
                width: '100%',
                padding: '10px 12px',
                background: 'transparent',
                border: 'none',
                color: '#a0a0a0',
                fontSize: '11px',
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
            padding: '0'
          }}>
            <button
              onClick={() => setExpandedSection(expandedSection === 'output' ? null : 'output')}
              style={{
                width: '100%',
                padding: '10px 12px',
                background: 'transparent',
                border: 'none',
                color: '#a0a0a0',
                fontSize: '11px',
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
            padding: '0'
          }}>
            <button
              onClick={() => setExpandedSection(expandedSection === 'example' ? null : 'example')}
              style={{
                width: '100%',
                padding: '10px 12px',
                background: 'transparent',
                border: 'none',
                color: '#a0a0a0',
                fontSize: '11px',
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

      {/* Legend */}
      <div style={{
        marginTop: '16px',
        padding: '12px',
        background: 'rgba(99, 102, 241, 0.1)',
        border: '1px solid rgba(99, 102, 241, 0.3)',
        borderRadius: '8px',
        fontSize: '9px',
        color: '#a0a0a0',
        lineHeight: '1.6'
      }}>
        <strong style={{ color: '#6366f1' }}>📖 How to read:</strong>
        <div style={{ marginTop: '6px' }}>
          🔹 <strong>INPUT:</strong> Type of data the button needs (e.g., "port: number")<br/>
          🔹 <strong>PROCESS:</strong> Steps that happen when you click<br/>
          🔹 <strong>OUTPUT:</strong> What you get back (e.g., "status: ✅ RUNNING")<br/>
          🔹 <strong>EXAMPLE:</strong> Real values showing how it works
        </div>
      </div>
    </div>
  )
}
