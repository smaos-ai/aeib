import { useEffect, useState } from 'react'

export default function EvidenceCompleteness() {
  const [animatedPercentages, setAnimatedPercentages] = useState({})

  const frameworks = [
    {
      id: 'eu-ai-act',
      name: '🇪🇺 EU AI Act',
      icon: '📋',
      collected: 4,
      total: 6,
      percentage: 67,
      color: '#3b82f6',
      evidence: [
        { item: 'Risk assessment report', completed: true },
        { item: 'Human oversight logs', completed: true },
        { item: 'Gate decision audit trail', completed: true },
        { item: 'Bias testing report', completed: true },
        { item: 'Transparency guide', completed: false },
        { item: 'Data impact assessment', completed: false }
      ],
      nextAction: 'Finalize transparency guide'
    },
    {
      id: 'cac-30',
      name: '🇨🇳 CAC 3.0',
      icon: '📄',
      collected: 2,
      total: 4,
      percentage: 50,
      color: '#ef4444',
      evidence: [
        { item: 'Intent verification logs', completed: true },
        { item: 'Data localization proof', completed: true },
        { item: 'Cryptographic audit trail', completed: false },
        { item: 'Incident reporting procedures', completed: false }
      ],
      nextAction: 'Complete cryptographic audit documentation'
    },
    {
      id: 'gdpr',
      name: '🇪🇺 GDPR',
      icon: '📋',
      collected: 6,
      total: 6,
      percentage: 100,
      color: '#10b981',
      evidence: [
        { item: 'Data minimization policy', completed: true },
        { item: 'Right to explanation guide', completed: true },
        { item: 'Data subject access procedures', completed: true },
        { item: 'Privacy-by-design documentation', completed: true },
        { item: 'Consent management system', completed: true },
        { item: 'Data retention policy', completed: true }
      ],
      nextAction: 'Schedule annual review'
    },
    {
      id: 'soc2',
      name: '🔐 SOC 2 Type II',
      icon: '🔒',
      collected: 5,
      total: 8,
      percentage: 63,
      color: '#a78bfa',
      evidence: [
        { item: 'Security controls audit', completed: true },
        { item: 'Availability uptime report', completed: true },
        { item: 'Confidentiality encryption policy', completed: true },
        { item: 'Incident response plan', completed: true },
        { item: 'Key rotation procedures', completed: true },
        { item: 'Penetration test report', completed: false },
        { item: 'Business continuity plan', completed: false },
        { item: 'Access control audit', completed: false }
      ],
      nextAction: 'Schedule penetration testing'
    }
  ]

  // Animate progress bars on mount
  useEffect(() => {
    const timer = setTimeout(() => {
      const percentages = {}
      frameworks.forEach(fw => {
        percentages[fw.id] = fw.percentage
      })
      setAnimatedPercentages(percentages)
    }, 200)
    return () => clearTimeout(timer)
  }, [])

  const getStatusBadge = (percentage) => {
    if (percentage === 100) {
      return { label: 'Complete', color: '#059669', bgColor: 'rgba(5, 150, 105, 0.2)', icon: '✅' }
    }
    if (percentage >= 67) {
      return { label: 'Near Complete', color: '#10b981', bgColor: 'rgba(16, 185, 129, 0.2)', icon: '🟢' }
    }
    if (percentage >= 34) {
      return { label: 'On Track', color: '#f59e0b', bgColor: 'rgba(245, 158, 11, 0.2)', icon: '🟡' }
    }
    return { label: 'Behind', color: '#ef4444', bgColor: 'rgba(239, 68, 68, 0.2)', icon: '🔴' }
  }

  const FrameworkCard = ({ framework }) => {
    const status = getStatusBadge(framework.percentage)
    const animatedPercent = animatedPercentages[framework.id] ?? 0

    return (
      <div
        style={{
          background: `linear-gradient(135deg, ${framework.color}12 0%, ${framework.color}06 100%)`,
          border: `1px solid ${framework.color}30`,
          borderRadius: '14px',
          padding: '18px',
          marginBottom: '16px',
          transition: 'all 0.3s ease',
          backdropFilter: 'blur(4px)'
        }}
      >
        {/* Header: Framework name + status badge */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '14px'
        }}>
          <div style={{
            fontSize: '13px',
            fontWeight: 'bold',
            color: framework.color,
            letterSpacing: '0.5px'
          }}>
            {framework.icon} {framework.name}
          </div>
          <div style={{
            background: status.bgColor,
            border: `1px solid ${status.color}`,
            borderRadius: '6px',
            padding: '4px 10px',
            fontSize: '11px',
            fontWeight: 'bold',
            color: status.color,
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}>
            {status.icon} {status.label}
          </div>
        </div>

        {/* Progress bar section */}
        <div style={{ marginBottom: '14px' }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '8px'
          }}>
            <div style={{
              fontSize: '11px',
              color: '#a0a0a0',
              fontWeight: '500'
            }}>
              Progress
            </div>
            <div style={{
              fontSize: '12px',
              fontWeight: 'bold',
              color: framework.color
            }}>
              {animatedPercent}%
            </div>
          </div>

          {/* Animated progress bar */}
          <div style={{
            background: 'rgba(0, 0, 0, 0.2)',
            borderRadius: '8px',
            height: '8px',
            overflow: 'hidden',
            border: `1px solid ${framework.color}20`
          }}>
            <div
              style={{
                background: `linear-gradient(90deg, ${framework.color} 0%, ${framework.color}cc 100%)`,
                height: '100%',
                width: `${animatedPercent}%`,
                transition: 'width 1.2s cubic-bezier(0.34, 1.56, 0.64, 1)',
                borderRadius: '8px',
                boxShadow: `0 0 12px ${framework.color}40`
              }}
            />
          </div>
        </div>

        {/* Document count */}
        <div style={{
          fontSize: '11px',
          color: '#a0a0a0',
          marginBottom: '14px',
          padding: '8px',
          background: 'rgba(0, 0, 0, 0.15)',
          borderRadius: '6px',
          borderLeft: `3px solid ${framework.color}`
        }}>
          <strong style={{ color: framework.color }}>
            {framework.collected} of {framework.total} documents
          </strong>
          {' '}collected
        </div>

        {/* Evidence items */}
        <div style={{ marginBottom: '12px' }}>
          <div style={{
            fontSize: '10px',
            fontWeight: 'bold',
            color: '#a0a0a0',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            marginBottom: '8px'
          }}>
            Evidence Items
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr',
            gap: '6px'
          }}>
            {framework.evidence.map((item, idx) => (
              <div
                key={idx}
                style={{
                  fontSize: '11px',
                  color: item.completed ? '#10b981' : '#a0a0a0',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '6px',
                  borderRadius: '4px',
                  background: item.completed ? 'rgba(16, 185, 129, 0.1)' : 'transparent',
                  textDecoration: item.completed ? 'none' : 'none',
                  opacity: item.completed ? 1 : 0.7
                }}
              >
                <span style={{ fontSize: '12px', fontWeight: 'bold' }}>
                  {item.completed ? '✅' : '❌'}
                </span>
                {item.item}
              </div>
            ))}
          </div>
        </div>

        {/* Next action */}
        <div style={{
          background: `${framework.color}15`,
          border: `1px solid ${framework.color}30`,
          borderRadius: '8px',
          padding: '10px',
          fontSize: '11px',
          color: '#a0a0a0'
        }}>
          <strong style={{ color: framework.color }}>Next Action: </strong>
          {framework.nextAction}
        </div>
      </div>
    )
  }

  const completedFrameworks = frameworks.filter(fw => fw.percentage === 100).length
  const totalProgress = Math.round(frameworks.reduce((acc, fw) => acc + fw.percentage, 0) / frameworks.length)

  return (
    <div style={{ padding: '0' }}>
      {/* Title */}
      <div style={{
        fontSize: '11px',
        fontWeight: 'bold',
        color: '#3b82f6',
        marginBottom: '16px',
        textTransform: 'uppercase',
        letterSpacing: '1px'
      }}>
        📊 Evidence Completeness Dashboard
      </div>

      {/* Overall progress card */}
      <div
        style={{
          background: 'linear-gradient(135deg, #3b82f615 0%, #10b98115 100%)',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          borderRadius: '14px',
          padding: '16px',
          marginBottom: '16px',
          backdropFilter: 'blur(4px)'
        }}
      >
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          gap: '12px',
          marginBottom: '14px'
        }}>
          <div style={{
            textAlign: 'center',
            padding: '10px',
            background: 'rgba(0, 0, 0, 0.1)',
            borderRadius: '8px'
          }}>
            <div style={{
              fontSize: '18px',
              fontWeight: 'bold',
              color: '#3b82f6'
            }}>
              {totalProgress}%
            </div>
            <div style={{
              fontSize: '9px',
              color: '#a0a0a0',
              marginTop: '4px'
            }}>
              Overall
            </div>
          </div>

          <div style={{
            textAlign: 'center',
            padding: '10px',
            background: 'rgba(0, 0, 0, 0.1)',
            borderRadius: '8px'
          }}>
            <div style={{
              fontSize: '18px',
              fontWeight: 'bold',
              color: '#10b981'
            }}>
              {completedFrameworks}/4
            </div>
            <div style={{
              fontSize: '9px',
              color: '#a0a0a0',
              marginTop: '4px'
            }}>
              Completed
            </div>
          </div>

          <div style={{
            textAlign: 'center',
            padding: '10px',
            background: 'rgba(0, 0, 0, 0.1)',
            borderRadius: '8px'
          }}>
            <div style={{
              fontSize: '18px',
              fontWeight: 'bold',
              color: '#f59e0b'
            }}>
              {frameworks.reduce((acc, fw) => acc + fw.collected, 0)}/24
            </div>
            <div style={{
              fontSize: '9px',
              color: '#a0a0a0',
              marginTop: '4px'
            }}>
              Documents
            </div>
          </div>
        </div>

        <div style={{
          fontSize: '10px',
          color: '#a0a0a0',
          lineHeight: '1.5',
          background: 'rgba(0, 0, 0, 0.15)',
          padding: '10px',
          borderRadius: '6px',
          borderLeft: '3px solid #3b82f6'
        }}>
          Track compliance evidence across all regulatory frameworks. Each framework shows collected documents, evidence items, and next actions needed for full compliance.
        </div>
      </div>

      {/* Framework cards */}
      <div style={{ marginBottom: '12px' }}>
        {frameworks.map((framework) => (
          <FrameworkCard key={framework.id} framework={framework} />
        ))}
      </div>

      {/* Action footer */}
      <div style={{
        background: 'rgba(16, 185, 129, 0.1)',
        border: '2px solid #10b981',
        borderRadius: '12px',
        padding: '14px',
        marginTop: '16px'
      }}>
        <div style={{
          fontSize: '11px',
          fontWeight: 'bold',
          color: '#10b981',
          marginBottom: '10px',
          textTransform: 'uppercase',
          letterSpacing: '1px'
        }}>
          ✅ Compliance Submission Timeline
        </div>

        <div style={{
          fontSize: '10px',
          color: '#a0a0a0',
          lineHeight: '1.6'
        }}>
          <div style={{ marginBottom: '8px', display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
            <span style={{ color: '#10b981', fontWeight: 'bold', minWidth: '140px' }}>EU AI Act:</span>
            <span>Submit Annex III by Dec 2, 2027 (Annex I by Aug 2, 2028)</span>
          </div>
          <div style={{ marginBottom: '8px', display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
            <span style={{ color: '#ef4444', fontWeight: 'bold', minWidth: '140px' }}>CAC 3.0:</span>
            <span>Immediate compliance active (Jul 15, 2026) ✅</span>
          </div>
          <div style={{ marginBottom: '8px', display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
            <span style={{ color: '#10b981', fontWeight: 'bold', minWidth: '140px' }}>GDPR:</span>
            <span>Ongoing compliance - ready for audit ✅</span>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
            <span style={{ color: '#a78bfa', fontWeight: 'bold', minWidth: '140px' }}>SOC 2 Type II:</span>
            <span>Schedule annual audit (5 of 8 docs ready)</span>
          </div>
        </div>
      </div>
    </div>
  )
}
