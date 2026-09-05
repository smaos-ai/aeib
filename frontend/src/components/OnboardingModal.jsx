import { useState } from 'react'

export default function OnboardingModal({ onClose }) {
  const [step, setStep] = useState(0);

  const steps = [
    {
      title: '🚀 Welcome to SMAOS',
      subtitle: 'Sovereign AI Operating System',
      description: 'A revolutionary system for running AI agents with real-time compliance monitoring and immutable audit trails.',
      icon: '🚀',
      color: '#3b82f6'
    },
    {
      title: '🔵 Phase 1: PRE-FLIGHT (Planning)',
      subtitle: 'Learn before you launch',
      description: 'Review the architecture, compliance requirements, and what each button does. Think of this like a preflight checklist on a real airplane — you verify everything works before takeoff.',
      icon: '🔵',
      color: '#2c3e50',
      details: [
        '📚 Architecture Guide — Understand how SMAOS works',
        '⚖️ Compliance Dashboard — See EU AI Act, CAC 3.0, GDPR, SOC 2',
        '📊 Evidence Tracker — Monitor compliance readiness (65% complete)',
        '📖 Button Guide — Learn INPUT/OUTPUT for each control'
      ]
    },
    {
      title: '🟡 Phase 2: LAUNCH (Ignition)',
      subtitle: 'Countdown to system start',
      description: 'Watch the system initialize. 6 subsystems boot in parallel with real-time progress. When all reach 100%, the system is "nominal" and ready to fly.',
      icon: '🟡',
      color: '#ff6b35',
      details: [
        'T-5 countdown timer',
        'Policy Engine initialization',
        'Knowledge Base loading (pgvector)',
        'Permit Gates arming',
        'MCP Servers connecting',
        'Infrastructure verification'
      ]
    },
    {
      title: '🟢 Phase 3: FLYING (Active)',
      subtitle: 'Monitor in real-time',
      description: 'System is live. Watch real-time metrics, run transaction simulations, see compliance gates in action. This is where the magic happens.',
      icon: '🟢',
      color: '#2ecc71',
      details: [
        '📈 Live Metrics — Token speed, memory, CPU, requests/min',
        '💳 Simulator — Run a real hotel booking transaction (8 steps)',
        '🔄 System Flows — See data isolation, compliance, proof trail',
        '🌳 Agent DAG — Watch step-by-step execution',
        '⚙️ Terminal — Live policy checks and compliance gates'
      ]
    },
    {
      title: '⬛ Phase 4: BLACK BOX (Archive)',
      subtitle: 'Immutable proof trail',
      description: 'Every action is logged with cryptographic signatures (Ed25519). Nothing can be changed. Perfect for regulators who need proof.',
      icon: '⬛',
      color: '#1c1c1c',
      details: [
        '📜 Flight Data Recorder — Immutable ledger of all actions',
        '🔐 Cryptographic Proofs — Ed25519 signatures on every entry',
        '📥 Export — Download flight recorder as JSON',
        '✅ Verification — Regulators can independently verify signatures'
      ]
    },
    {
      title: '💡 Pro Tips',
      subtitle: 'Get the most out of SMAOS',
      description: 'Navigate the system like a pro.',
      icon: '💡',
      color: '#f59e0b',
      details: [
        '📍 Phase Navigator (top) — Shows current phase and progress',
        '? Help Button (top right) — More details on any metric',
        '⌨️ Keyboard Tab — Navigate buttons with Tab + Enter',
        '📥 Download Proofs — Export ledger for regulators',
        '🔄 Reset Anytime — Click Reset to start over'
      ]
    },
    {
      title: '🎯 You\'re Ready!',
      subtitle: 'Let\'s launch',
      description: 'You now understand the 4-phase journey. Click "Let\'s Go" to start the PRE-FLIGHT phase and explore SMAOS.',
      icon: '✨',
      color: '#10b981'
    }
  ];

  const current = steps[step];

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.8)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 3000,
      backdropFilter: 'blur(8px)'
    }}>
      <dialog
        open={true}
        style={{
          border: 'none',
          background: 'transparent',
          padding: 0,
          maxWidth: '600px',
          width: '90%'
        }}
        aria-labelledby="onboarding-title"
        aria-modal="true"
      >
        <div style={{
          background: `linear-gradient(135deg, ${current.color}20 0%, ${current.color}10 100%)`,
          border: `2px solid ${current.color}`,
          borderRadius: '16px',
          padding: '40px',
          backdropFilter: 'blur(8px)',
          textAlign: 'center'
        }}>
          {/* Icon */}
          <div style={{
            fontSize: '64px',
            marginBottom: '16px'
          }}>
            {current.icon}
          </div>

          {/* Title */}
          <h2
            id="onboarding-title"
            style={{
              fontSize: '28px',
              fontWeight: 'bold',
              color: '#fff',
              margin: '0 0 8px 0'
            }}
          >
            {current.title}
          </h2>

          {/* Subtitle */}
          <div style={{
            fontSize: '14px',
            color: current.color,
            marginBottom: '16px',
            fontWeight: 'bold',
            textTransform: 'uppercase',
            letterSpacing: '1px'
          }}>
            {current.subtitle}
          </div>

          {/* Description */}
          <p style={{
            fontSize: '14px',
            color: '#a0a0a0',
            marginBottom: '20px',
            lineHeight: '1.6'
          }}>
            {current.description}
          </p>

          {/* Details (if any) */}
          {current.details && (
            <div style={{
              background: 'rgba(0, 0, 0, 0.3)',
              borderRadius: '8px',
              padding: '16px',
              marginBottom: '20px',
              textAlign: 'left'
            }}>
              {current.details.map((detail, i) => (
                <div
                  key={i}
                  style={{
                    fontSize: '12px',
                    color: '#c5c5c5',
                    marginBottom: i < current.details.length - 1 ? '8px' : '0',
                    paddingLeft: '0'
                  }}
                >
                  {detail}
                </div>
              ))}
            </div>
          )}

          {/* Progress Indicator */}
          <div style={{
            display: 'flex',
            gap: '8px',
            justifyContent: 'center',
            marginBottom: '24px'
          }}>
            {steps.map((_, i) => (
              <div
                key={i}
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: i === step ? current.color : 'rgba(255, 255, 255, 0.2)',
                  transition: 'background 0.3s'
                }}
              />
            ))}
          </div>

          {/* Buttons */}
          <div style={{
            display: 'flex',
            gap: '12px',
            justifyContent: 'center'
          }}>
            {step > 0 && (
              <button
                onClick={() => setStep(step - 1)}
                style={{
                  padding: '10px 20px',
                  background: 'rgba(100, 116, 139, 0.2)',
                  border: '1px solid rgba(100, 116, 139, 0.3)',
                  borderRadius: '8px',
                  color: '#a0a0a0',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  outline: 'none'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(100, 116, 139, 0.3)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'rgba(100, 116, 139, 0.2)';
                }}
                onFocus={(e) => {
                  e.currentTarget.style.outline = '2px solid #3b82f6';
                  e.currentTarget.style.outlineOffset = '2px';
                }}
                onBlur={(e) => {
                  e.currentTarget.style.outline = 'none';
                }}
              >
                ← Back
              </button>
            )}

            {step < steps.length - 1 && (
              <button
                onClick={() => setStep(step + 1)}
                style={{
                  flex: 1,
                  padding: '10px 20px',
                  background: `linear-gradient(135deg, ${current.color} 0%, ${current.color}dd 100%)`,
                  border: 'none',
                  borderRadius: '8px',
                  color: '#fff',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  outline: 'none'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = `0 8px 16px ${current.color}40`;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
                onFocus={(e) => {
                  e.currentTarget.style.outline = '2px solid #fff';
                  e.currentTarget.style.outlineOffset = '2px';
                }}
                onBlur={(e) => {
                  e.currentTarget.style.outline = 'none';
                }}
              >
                Next →
              </button>
            )}

            {step === steps.length - 1 && (
              <button
                onClick={onClose}
                style={{
                  flex: 1,
                  padding: '10px 20px',
                  background: `linear-gradient(135deg, ${current.color} 0%, ${current.color}dd 100%)`,
                  border: 'none',
                  borderRadius: '8px',
                  color: '#fff',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  outline: 'none'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = `0 8px 16px ${current.color}40`;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
                onFocus={(e) => {
                  e.currentTarget.style.outline = '2px solid #fff';
                  e.currentTarget.style.outlineOffset = '2px';
                }}
                onBlur={(e) => {
                  e.currentTarget.style.outline = 'none';
                }}
              >
                🚀 Let's Go!
              </button>
            )}
          </div>

          {/* Skip button */}
          <button
            onClick={onClose}
            style={{
              marginTop: '16px',
              background: 'none',
              border: 'none',
              color: '#475569',
              fontSize: '12px',
              cursor: 'pointer',
              textDecoration: 'underline',
              outline: 'none'
            }}
            onFocus={(e) => {
              e.currentTarget.style.outline = '2px solid #3b82f6';
              e.currentTarget.style.outlineOffset = '2px';
            }}
            onBlur={(e) => {
              e.currentTarget.style.outline = 'none';
            }}
          >
            Skip intro
          </button>
        </div>
      </dialog>
    </div>
  );
}
