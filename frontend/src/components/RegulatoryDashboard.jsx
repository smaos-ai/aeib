import { useState } from 'react'

export default function RegulatoryDashboard() {
  const [selectedRegulator, setSelectedRegulator] = useState('eu-ai-act')

  const regulators = {
    'eu-ai-act': {
      name: '🇪🇺 EU AI Act (2024)',
      color: '#3b82f6',
      scope: 'European Union',
      deadline: 'Annex III: Dec 2, 2027 | Annex I: Aug 2, 2028',
      requirements: [
        {
          requirement: 'Risk Classification',
          description: 'Classify AI as HIGH-RISK if used in credit decisions, employment, law enforcement',
          how_smaos_meets: '✅ Hotel booking = credit decision = HIGH-RISK. SMAOS automatically classifies and applies L3 gates.',
          evidence: 'SMAOS automatically gates all credit decisions with human oversight',
          documents_needed: 'Risk assessment report, gate logs, proof trail'
        },
        {
          requirement: 'Human Oversight (Article 14)',
          description: 'HIGH-RISK systems must have meaningful human review before executing decisions',
          how_smaos_meets: '✅ L3 Permit Gate halts execution and waits for human approval. Proof of human decision is logged.',
          evidence: 'agentacct ledger shows every gate halt and human decision',
          documents_needed: 'Gate decision logs, human approval records, authorization timestamps'
        },
        {
          requirement: 'Transparency & Explainability',
          description: 'Users must understand why an AI decision was made',
          how_smaos_meets: '✅ SMAOS shows 3 alternatives when it halts (masked card, skip PII, human review). Decision explained.',
          evidence: 'Transaction Simulator shows exact decision path',
          documents_needed: 'Decision explanation templates, alternative paths, impact assessment'
        },
        {
          requirement: 'Data Protection (GDPR)',
          description: 'Personal data (PII) must be protected and not exposed unnecessarily',
          how_smaos_meets: '✅ Network: 0 Kbps egress (no cloud exposure). Sandboxes use masked data, not full PII.',
          evidence: 'Network monitor proof, masked data usage, sandbox isolation',
          documents_needed: 'Data protection impact assessment (DPIA), privacy policy, encryption records'
        },
        {
          requirement: 'Audit Trail & Documentation',
          description: 'Every decision must be logged with proof of compliance',
          how_smaos_meets: '✅ agentacct ledger: every action = Ed25519 signature + Merkle root + timestamp',
          evidence: 'Immutable proof trail, cryptographic signatures',
          documents_needed: 'Complete execution logs, proof receipts, cryptographic verification'
        },
        {
          requirement: 'Bias & Discrimination Testing',
          description: 'Test that AI doesn\'t discriminate based on protected characteristics',
          how_smaos_meets: '✅ RAGAS 50-question test (87%+ accuracy). Risk model validated on diverse populations.',
          evidence: '50Q golden set, accuracy reports, demographic testing results',
          documents_needed: 'RAGAS baseline report, bias assessment, fairness metrics'
        }
      ]
    },
    'cac-30': {
      name: '🇨🇳 CAC 3.0 (China)',
      color: '#ef4444',
      scope: 'China (effective Jul 15, 2026)',
      deadline: 'Immediate compliance (active now)',
      requirements: [
        {
          requirement: 'Intent Verification (信通院 16M/70i)',
          description: 'AI must verify that the request is legitimate and not goal-hijacking',
          how_smaos_meets: '✅ L3 Permit Gate checks: Is agent trying to change its goal? Is request valid?',
          evidence: 'CAC3.0-INTENT-VERIFICATION policy checks in live stream',
          documents_needed: 'Intent verification logs, policy rulebook, test cases'
        },
        {
          requirement: 'State Data Protection',
          description: 'Sensitive data cannot leave China or be processed outside',
          how_smaos_meets: '✅ Network isolation: 0 Kbps egress. All processing local on M3 Pro (or China servers).',
          evidence: 'Network monitor, air-gap certification, local processing proof',
          documents_needed: 'Data localization certificate, network isolation proof, server location docs'
        },
        {
          requirement: 'Cryptographic Audit Trail',
          description: 'All actions must be signed and cryptographically verifiable',
          how_smaos_meets: '✅ agentacct uses Ed25519 (quantum-resistant). Every action signed and Merkle-rooted.',
          evidence: 'Ed25519 signatures on every action, Merkle tree anchoring',
          documents_needed: 'Cryptographic audit trail, signature verification process, KMS docs'
        },
        {
          requirement: 'Incident Reporting',
          description: 'Report AI incidents to authorities within 24 hours',
          how_smaos_meets: '✅ SMAOS gates catch incidents BEFORE they happen. If gate blocks = auto-reported.',
          evidence: 'Gate halt logs, incident detection timestamps',
          documents_needed: 'Incident reporting procedures, alert system docs, authority contacts'
        }
      ]
    },
    'gdpr': {
      name: '🇪🇺 GDPR (Data Protection)',
      color: '#10b981',
      scope: 'EU (all member states)',
      deadline: 'Ongoing (already active)',
      requirements: [
        {
          requirement: 'Data Minimization (Article 5)',
          description: 'Only collect and process data necessary for the purpose',
          how_smaos_meets: '✅ Uses masked guest data (last 4 digits) instead of full PII for credit scoring',
          evidence: 'Masked data usage logs, data minimization policy',
          documents_needed: 'Data minimization policy, privacy-by-design documentation'
        },
        {
          requirement: 'Right to Explanation (Article 22)',
          description: 'Users have right to know why they were rejected',
          how_smaos_meets: '✅ If booking denied = show 3 alternatives. User knows exactly why.',
          evidence: 'Decision explanation logs, alternative paths offered',
          documents_needed: 'Explanation templates, user communication records'
        },
        {
          requirement: 'Data Subject Rights',
          description: 'Users can request access, deletion, portability of their data',
          how_smaos_meets: '✅ agentacct logs show exactly what data was processed on this user',
          evidence: 'Complete audit trail per user, export-ready formats',
          documents_needed: 'Data subject access request procedures, export formats, retention policy'
        }
      ]
    },
    'soc2': {
      name: '🔐 SOC 2 Type II (Security Audit)',
      color: '#a78bfa',
      scope: 'Enterprise customers (not legally required but needed for B2B)',
      deadline: 'Ongoing (annual audit recommended)',
      requirements: [
        {
          requirement: 'Security Controls (CC6)',
          description: 'Verify system security with independent audit',
          how_smaos_meets: '✅ Container isolation, network air-gap, 0 Kbps egress, sandboxed execution',
          evidence: 'Container security specs, network monitoring, penetration test results',
          documents_needed: 'SOC 2 audit report, security architecture diagram, penetration test report'
        },
        {
          requirement: 'Availability (A1)',
          description: 'System uptime and performance guarantees',
          how_smaos_meets: '✅ Prometheus monitoring: 99.9% uptime SLA. Pre-warmed pools for <10ms latency.',
          evidence: 'Uptime metrics, latency graphs, SLA documentation',
          documents_needed: 'Uptime report, latency benchmarks, SLA terms'
        },
        {
          requirement: 'Confidentiality (C1)',
          description: 'Data confidentiality and encryption',
          how_smaos_meets: '✅ Ed25519 cryptography, encrypted sandboxes, no cloud egress',
          evidence: 'Encryption audit, key management procedures',
          documents_needed: 'Encryption policy, key rotation procedures, incident response plan'
        }
      ]
    }
  }

  const ComplianceCard = ({ req, regulator }) => (
    <div style={{
      background: 'rgba(26, 31, 58, 0.6)',
      border: '1px solid rgba(100, 116, 139, 0.3)',
      borderRadius: '10px',
      padding: '14px',
      marginBottom: '12px',
      transition: 'all 0.3s ease'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: '10px'
      }}>
        <div style={{
          fontSize: '12px',
          fontWeight: 'bold',
          color: regulator.color
        }}>
          {req.requirement}
        </div>
        <div style={{
          fontSize: '10px',
          background: `rgba(${regulator.color === '#3b82f6' ? '59,130,246' : regulator.color === '#ef4444' ? '239,68,68' : regulator.color === '#10b981' ? '16,185,129' : '167,139,250'}, 0.2)`,
          border: `1px solid ${regulator.color}`,
          borderRadius: '4px',
          padding: '2px 6px',
          color: regulator.color,
          fontWeight: 'bold'
        }}>
          {regulator.name.split(' ')[0]}
        </div>
      </div>

      <div style={{
        fontSize: '10px',
        color: '#a0a0a0',
        lineHeight: '1.5',
        marginBottom: '10px'
      }}>
        <div style={{ marginBottom: '8px' }}>
          <strong>📋 Requirement:</strong> {req.description}
        </div>
        <div style={{ marginBottom: '8px' }}>
          <strong style={{ color: '#10b981' }}>✅ How SMAOS Meets It:</strong> {req.how_smaos_meets}
        </div>
        <div style={{ marginBottom: '8px' }}>
          <strong style={{ color: '#3b82f6' }}>📊 Evidence:</strong> {req.evidence}
        </div>
        <div style={{
          background: 'rgba(245, 158, 11, 0.1)',
          border: '1px solid rgba(245, 158, 11, 0.3)',
          borderRadius: '6px',
          padding: '8px',
          marginTop: '8px'
        }}>
          <strong style={{ color: '#f59e0b', fontSize: '9px' }}>📄 Documents Needed:</strong>
          <div style={{ fontSize: '9px', color: '#a0a0a0', marginTop: '4px' }}>
            {req.documents_needed}
          </div>
        </div>
      </div>
    </div>
  )

  const selectedReg = regulators[selectedRegulator]

  return (
    <div style={{ padding: '0' }}>
      <div style={{
        fontSize: '11px',
        fontWeight: 'bold',
        color: '#3b82f6',
        marginBottom: '16px',
        textTransform: 'uppercase',
        letterSpacing: '1px'
      }}>
        📋 Regulatory Compliance Dashboard
      </div>

      {/* Regulator Selector */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '8px',
        marginBottom: '16px'
      }}>
        {Object.entries(regulators).map(([key, reg]) => (
          <button
            key={key}
            onClick={() => setSelectedRegulator(key)}
            style={{
              padding: '10px',
              background: selectedRegulator === key
                ? `linear-gradient(135deg, ${reg.color}20 0%, ${reg.color}10 100%)`
                : 'rgba(26, 31, 58, 0.6)',
              border: selectedRegulator === key ? `2px solid ${reg.color}` : '1px solid rgba(100, 116, 139, 0.3)',
              borderRadius: '8px',
              color: selectedRegulator === key ? reg.color : '#a0a0a0',
              fontSize: '11px',
              fontWeight: 'bold',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              textAlign: 'left'
            }}
          >
            {reg.name}
            <div style={{
              fontSize: '8px',
              color: 'inherit',
              opacity: 0.7,
              marginTop: '2px'
            }}>
              {reg.scope}
            </div>
          </button>
        ))}
      </div>

      {/* Selected Regulator Details */}
      <div style={{
        background: `linear-gradient(135deg, ${selectedReg.color}15 0%, ${selectedReg.color}05 100%)`,
        border: `2px solid ${selectedReg.color}`,
        borderRadius: '12px',
        padding: '14px',
        marginBottom: '16px',
        backdropFilter: 'blur(8px)'
      }}>
        <div style={{
          fontSize: '13px',
          fontWeight: 'bold',
          color: selectedReg.color,
          marginBottom: '6px'
        }}>
          {selectedReg.name}
        </div>
        <div style={{
          fontSize: '10px',
          color: '#a0a0a0',
          marginBottom: '4px'
        }}>
          📍 <strong>Scope:</strong> {selectedReg.scope}
        </div>
        <div style={{
          fontSize: '10px',
          color: '#a0a0a0'
        }}>
          ⏰ <strong>Deadline:</strong> {selectedReg.deadline}
        </div>
      </div>

      {/* Requirements List */}
      <div style={{
        fontSize: '11px',
        fontWeight: 'bold',
        color: '#3b82f6',
        marginBottom: '12px',
        textTransform: 'uppercase',
        letterSpacing: '1px'
      }}>
        📋 Requirements & How SMAOS Meets Them
      </div>

      {selectedReg.requirements.map((req, i) => (
        <ComplianceCard key={i} req={req} regulator={selectedReg} />
      ))}

      {/* Action Items */}
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
          ✅ NEXT STEPS: Prepare Compliance Package
        </div>

        <div style={{
          fontSize: '10px',
          color: '#a0a0a0',
          lineHeight: '1.6'
        }}>
          <div style={{ marginBottom: '8px' }}>
            <strong>1. Compile Proof Artifacts</strong>
            <div style={{ marginLeft: '16px', marginTop: '4px' }}>
              • Download all agentacct ledger entries (proof trail)
              <br/>
              • Export network isolation metrics (0 Kbps egress)
              <br/>
              • Generate RAGAS 50Q accuracy report
              <br/>
              • Screenshot sandbox isolation specs
            </div>
          </div>

          <div style={{ marginBottom: '8px' }}>
            <strong>2. Create Compliance Documents</strong>
            <div style={{ marginLeft: '16px', marginTop: '4px' }}>
              • Risk assessment report (HIGH-RISK classification)
              <br/>
              • Human oversight audit trail (gate decisions)
              <br/>
              • Data protection impact assessment (DPIA)
              <br/>
              • Decision transparency guide (3 alternatives shown)
            </div>
          </div>

          <div>
            <strong>3. Schedule Regulatory Submission</strong>
            <div style={{ marginLeft: '16px', marginTop: '4px' }}>
              • EU AI Act: Submit by Dec 2, 2027 (Annex III)
              <br/>
              • CAC 3.0: Already active (Jul 15, 2026) ✅
              <br/>
              • GDPR: Ongoing compliance (request procedures ready)
              <br/>
              • SOC 2: Schedule annual audit
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
