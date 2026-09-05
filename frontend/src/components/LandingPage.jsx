import { useState } from 'react'

export default function LandingPage({ onEnterDashboard }) {
  const [hoveredCard, setHoveredCard] = useState(null)

  const personas = [
    {
      role: 'Compliance Officer',
      icon: '⚖️',
      pain: 'Manual compliance tracking across 4 frameworks',
      need: 'Automated proof of compliance',
      color: '#a78bfa'
    },
    {
      role: 'AI/ML Engineer',
      icon: '🤖',
      pain: 'Building safe AI systems is hard',
      need: 'Built-in governance & gates',
      color: '#3b82f6'
    },
    {
      role: 'CTO/VP Engineering',
      icon: '🏗️',
      pain: '"Is our AI safe?" tough to answer',
      need: 'Real-time proof & visibility',
      color: '#10b981'
    },
    {
      role: 'Investor/VC',
      icon: '💰',
      pain: 'AI startups have regulatory risk',
      need: 'Proof of compliance & governance',
      color: '#f59e0b'
    }
  ]

  const problems = [
    {
      icon: '❌',
      title: 'Manual Compliance',
      desc: 'Checking EU AI Act, CAC 3.0, GDPR, SOC 2 manually',
      impact: '80 hours/month wasted'
    },
    {
      icon: '🎯',
      title: 'No Proof Trail',
      desc: 'Regulators ask "how do I know you\'re compliant?"',
      impact: 'Can\'t answer with confidence'
    },
    {
      icon: '⚡',
      title: 'Black Box AI',
      desc: 'Can\'t see what your AI is doing in real-time',
      impact: 'High regulatory & business risk'
    },
    {
      icon: '🔒',
      title: 'Data Exposure',
      desc: 'Traditional AI systems leak data to cloud',
      impact: 'GDPR violations, lawsuits'
    },
    {
      icon: '📊',
      title: 'No Metrics',
      desc: 'No way to measure compliance or safety',
      impact: 'Investors nervous, can\'t fundraise'
    },
    {
      icon: '🚫',
      title: 'Gate Enforcement',
      desc: 'AI can access sensitive data without checks',
      impact: 'Human oversight = slow & manual'
    }
  ]

  const solutions = [
    {
      icon: '🔐',
      title: 'Real-Time Compliance',
      desc: 'Automatic checks against all frameworks',
      benefit: 'Know instantly if compliant',
      color: '#10b981'
    },
    {
      icon: '📜',
      title: 'Immutable Proof',
      desc: 'Cryptographic signatures on every action',
      benefit: 'Regulators can verify independently',
      color: '#3b82f6'
    },
    {
      icon: '👁️',
      title: 'Live Visibility',
      desc: 'See every step your AI takes',
      benefit: 'Transparency builds trust',
      color: '#a78bfa'
    },
    {
      icon: '🎯',
      title: 'Autonomous Gates',
      desc: 'AI stops itself when rules violated',
      benefit: 'No human needed, instant halt',
      color: '#f59e0b'
    },
    {
      icon: '🏝️',
      title: 'Zero Egress',
      desc: 'Your data never leaves your infrastructure',
      benefit: 'GDPR compliant, sovereign AI',
      color: '#06b6d4'
    },
    {
      icon: '📈',
      title: 'Measurable',
      desc: 'Dashboard shows compliance metrics',
      benefit: 'Investors see real governance',
      color: '#ec4899'
    }
  ]

  const outcomes = [
    { metric: '98%', label: 'Compliance Automation', desc: 'vs 20% manually' },
    { metric: '0', label: 'Regulatory Violations', desc: 'Caught & blocked instantly' },
    { metric: '100%', label: 'Proof Trail', desc: 'Immutable, verifiable by regulators' },
    { metric: '50%', label: 'Time Saved', desc: 'No more manual compliance work' },
    { metric: '4x', label: 'Faster Fundraising', desc: 'Proof impresses investors' },
    { metric: '1', label: 'System of Record', desc: 'Single source of truth' }
  ]

  return (
    <div style={{
      background: 'linear-gradient(180deg, #0a0e27 0%, #1a1f3a 100%)',
      color: '#e0e0e0',
      overflow: 'auto',
      minHeight: '100vh',
      paddingBottom: '40px'
    }}>
      {/* HERO SECTION - "Podium" Effect */}
      <div style={{
        position: 'relative',
        padding: '60px 24px',
        textAlign: 'center',
        background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(168, 139, 250, 0.1) 100%)',
        borderBottom: '2px solid rgba(59, 130, 246, 0.3)',
        overflow: 'hidden'
      }}>
        {/* Animated background */}
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'radial-gradient(circle at 30% 30%, rgba(59, 130, 246, 0.05) 0%, transparent 50%)',
          pointerEvents: 'none'
        }} />

        <div style={{ position: 'relative', zIndex: 10, maxWidth: '900px', margin: '0 auto' }}>
          {/* Main Headline */}
          <div style={{
            fontSize: '48px',
            fontWeight: 'bold',
            marginBottom: '16px',
            background: 'linear-gradient(135deg, #3b82f6 0%, #a78bfa 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text'
          }}>
            🚀 SMAOS
          </div>

          <div style={{
            fontSize: '32px',
            fontWeight: 'bold',
            marginBottom: '20px',
            lineHeight: '1.4'
          }}>
            Sovereign AI Operating System
          </div>

          <div style={{
            fontSize: '16px',
            color: '#a0a0a0',
            marginBottom: '32px',
            lineHeight: '1.6',
            maxWidth: '700px',
            margin: '0 auto 32px'
          }}>
            The only AI system that is <strong style={{ color: '#10b981' }}>compliant by design</strong>,<br/>
            <strong style={{ color: '#3b82f6' }}>proven with cryptographic proof</strong>,<br/>
            and <strong style={{ color: '#f59e0b' }}>visible in real-time</strong>.
          </div>

          {/* CTA Button */}
          <button
            onClick={onEnterDashboard}
            style={{
              padding: '14px 32px',
              background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
              border: 'none',
              borderRadius: '8px',
              color: '#fff',
              fontSize: '14px',
              fontWeight: 'bold',
              cursor: 'pointer',
              transition: 'all 0.3s',
              boxShadow: '0 8px 24px rgba(59, 130, 246, 0.3)',
              outline: 'none'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-4px)'
              e.currentTarget.style.boxShadow = '0 12px 32px rgba(59, 130, 246, 0.5)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.boxShadow = '0 8px 24px rgba(59, 130, 246, 0.3)'
            }}
            onFocus={(e) => {
              e.currentTarget.style.outline = '2px solid #fff'
              e.currentTarget.style.outlineOffset = '2px'
            }}
            onBlur={(e) => {
              e.currentTarget.style.outline = 'none'
            }}
          >
            ▶ Enter Interactive Demo
          </button>

          <div style={{
            fontSize: '11px',
            color: '#666',
            marginTop: '16px'
          }}>
            🎬 5-minute journey through 4 phases: Learn → Launch → Monitor → Archive
          </div>
        </div>
      </div>

      {/* WHO IT'S FOR */}
      <div style={{ padding: '60px 24px', maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{
          fontSize: '24px',
          fontWeight: 'bold',
          marginBottom: '12px',
          color: '#fff'
        }}>
          👥 Built for AI Leaders
        </div>

        <div style={{
          fontSize: '14px',
          color: '#a0a0a0',
          marginBottom: '32px',
          maxWidth: '600px'
        }}>
          Four personas, one solution that solves their biggest problem.
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '16px'
        }}>
          {personas.map((p, i) => (
            <div
              key={i}
              onMouseEnter={() => setHoveredCard(`persona-${i}`)}
              onMouseLeave={() => setHoveredCard(null)}
              style={{
                padding: '20px',
                background: 'rgba(26, 31, 58, 0.8)',
                border: `2px solid ${hoveredCard === `persona-${i}` ? p.color : 'rgba(100, 116, 139, 0.3)'}`,
                borderRadius: '12px',
                transition: 'all 0.3s',
                cursor: 'pointer',
                transform: hoveredCard === `persona-${i}` ? 'translateY(-4px)' : 'translateY(0)'
              }}
            >
              <div style={{ fontSize: '32px', marginBottom: '12px' }}>{p.icon}</div>
              <div style={{ fontSize: '14px', fontWeight: 'bold', color: p.color, marginBottom: '8px' }}>
                {p.role}
              </div>
              <div style={{ fontSize: '12px', color: '#a0a0a0', marginBottom: '12px', lineHeight: '1.5' }}>
                <strong>Pain:</strong> {p.pain}
              </div>
              <div style={{ fontSize: '12px', color: '#10b981' }}>
                <strong>Need:</strong> {p.need}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* PROBLEMS WE SOLVE */}
      <div style={{
        padding: '60px 24px',
        maxWidth: '1200px',
        margin: '0 auto',
        background: 'linear-gradient(135deg, rgba(168, 139, 250, 0.05) 0%, transparent 100%)',
        borderTop: '1px solid rgba(100, 116, 139, 0.2)'
      }}>
        <div style={{
          fontSize: '24px',
          fontWeight: 'bold',
          marginBottom: '12px',
          color: '#fff'
        }}>
          ❌ The Problem Today
        </div>

        <div style={{
          fontSize: '14px',
          color: '#a0a0a0',
          marginBottom: '32px',
          maxWidth: '600px'
        }}>
          AI compliance is broken. Here's what keeps you up at night.
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '16px'
        }}>
          {problems.map((p, i) => (
            <div
              key={i}
              style={{
                padding: '20px',
                background: 'rgba(30, 41, 59, 0.8)',
                border: '1px solid rgba(239, 68, 68, 0.2)',
                borderRadius: '8px'
              }}
            >
              <div style={{ fontSize: '24px', marginBottom: '8px' }}>{p.icon}</div>
              <div style={{ fontSize: '14px', fontWeight: 'bold', color: '#ef4444', marginBottom: '8px' }}>
                {p.title}
              </div>
              <div style={{ fontSize: '12px', color: '#a0a0a0', marginBottom: '12px' }}>
                {p.desc}
              </div>
              <div style={{ fontSize: '11px', color: '#ef4444', fontStyle: 'italic' }}>
                💸 Impact: {p.impact}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* OUR SOLUTION */}
      <div style={{ padding: '60px 24px', maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{
          fontSize: '24px',
          fontWeight: 'bold',
          marginBottom: '12px',
          color: '#fff'
        }}>
          ✅ Our Solution
        </div>

        <div style={{
          fontSize: '14px',
          color: '#a0a0a0',
          marginBottom: '32px',
          maxWidth: '600px'
        }}>
          6 core capabilities that solve every problem above.
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '16px'
        }}>
          {solutions.map((s, i) => (
            <div
              key={i}
              onMouseEnter={() => setHoveredCard(`solution-${i}`)}
              onMouseLeave={() => setHoveredCard(null)}
              style={{
                padding: '24px',
                background: `linear-gradient(135deg, ${s.color}15 0%, ${s.color}05 100%)`,
                border: `2px solid ${hoveredCard === `solution-${i}` ? s.color : `${s.color}40`}`,
                borderRadius: '12px',
                transition: 'all 0.3s',
                cursor: 'pointer'
              }}
            >
              <div style={{ fontSize: '32px', marginBottom: '12px' }}>{s.icon}</div>
              <div style={{ fontSize: '14px', fontWeight: 'bold', color: s.color, marginBottom: '8px' }}>
                {s.title}
              </div>
              <div style={{ fontSize: '12px', color: '#a0a0a0', marginBottom: '12px', lineHeight: '1.5' }}>
                {s.desc}
              </div>
              <div style={{ fontSize: '12px', color: s.color, fontWeight: 'bold' }}>
                ✓ {s.benefit}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* OUTCOMES */}
      <div style={{
        padding: '60px 24px',
        maxWidth: '1200px',
        margin: '0 auto',
        background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.05) 0%, transparent 100%)',
        borderTop: '1px solid rgba(100, 116, 139, 0.2)'
      }}>
        <div style={{
          fontSize: '24px',
          fontWeight: 'bold',
          marginBottom: '12px',
          color: '#fff'
        }}>
          🎯 What You Get
        </div>

        <div style={{
          fontSize: '14px',
          color: '#a0a0a0',
          marginBottom: '32px',
          maxWidth: '600px'
        }}>
          Real, measurable outcomes that matter to your business.
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px'
        }}>
          {outcomes.map((o, i) => (
            <div
              key={i}
              style={{
                padding: '24px',
                background: 'rgba(16, 185, 129, 0.1)',
                border: '2px solid rgba(16, 185, 129, 0.3)',
                borderRadius: '8px',
                textAlign: 'center'
              }}
            >
              <div style={{
                fontSize: '32px',
                fontWeight: 'bold',
                color: '#10b981',
                marginBottom: '8px'
              }}>
                {o.metric}
              </div>
              <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#fff', marginBottom: '4px' }}>
                {o.label}
              </div>
              <div style={{ fontSize: '11px', color: '#a0a0a0' }}>
                {o.desc}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* FINAL CTA */}
      <div style={{
        padding: '60px 24px',
        textAlign: 'center',
        background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(168, 139, 250, 0.1) 100%)',
        borderTop: '2px solid rgba(59, 130, 246, 0.3)',
        borderBottom: '2px solid rgba(59, 130, 246, 0.3)'
      }}>
        <div style={{
          fontSize: '28px',
          fontWeight: 'bold',
          marginBottom: '16px',
          color: '#fff'
        }}>
          Ready to See It in Action?
        </div>

        <div style={{
          fontSize: '14px',
          color: '#a0a0a0',
          marginBottom: '32px'
        }}>
          Experience the 4-phase journey: Learn → Launch → Monitor → Archive
        </div>

        <button
          onClick={onEnterDashboard}
          style={{
            padding: '16px 40px',
            background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
            border: 'none',
            borderRadius: '8px',
            color: '#fff',
            fontSize: '15px',
            fontWeight: 'bold',
            cursor: 'pointer',
            transition: 'all 0.3s',
            boxShadow: '0 8px 24px rgba(59, 130, 246, 0.3)',
            outline: 'none'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-4px)'
            e.currentTarget.style.boxShadow = '0 12px 32px rgba(59, 130, 246, 0.5)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)'
            e.currentTarget.style.boxShadow = '0 8px 24px rgba(59, 130, 246, 0.3)'
          }}
          onFocus={(e) => {
            e.currentTarget.style.outline = '2px solid #fff'
            e.currentTarget.style.outlineOffset = '2px'
          }}
          onBlur={(e) => {
            e.currentTarget.style.outline = 'none'
          }}
        >
          🚀 Launch Interactive Demo (5 min)
        </button>
      </div>
    </div>
  )
}
