import React, { useState, useEffect } from 'react'
import { Button, FormGroup, InputGroup, HTMLSelect, Card, H4, ProgressBar, Tag, Tooltip, Intent } from '@blueprintjs/core'
import { getCapsule } from '../../lib/capsules'
import { classifyIntent } from '../../lib/riskClassifier'
import { useGovernance } from '../../state/GovernanceContext'

export default function LeftIntentPane() {
  const { state, submitIntent, classifyIntent: dispatchClassify, setCapsule } = useGovernance()
  const capsule = getCapsule(state.capsuleId)
  const [fields, setFields] = useState({})
  const [classification, setClassification] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [focusedField, setFocusedField] = useState(null)
  const [previewClassification, setPreviewClassification] = useState(null)

  const handleFieldChange = (fieldName, value) => {
    setFields(prev => ({ ...prev, [fieldName]: value }))

    // Real-time preview classification
    const updated = { ...fields, [fieldName]: value }
    const preview = classifyIntent(capsule, updated)
    setPreviewClassification(preview)
  }

  const handleCapsuleChange = (e) => {
    setCapsule(e.target.value)
    setFields({})
    setClassification(null)
    setPreviewClassification(null)
  }

  const handleSubmit = () => {
    try {
      if (!capsule) {
        console.error('ERROR: capsule is undefined', { capsuleId: state.capsuleId })
        alert('ERROR: Capsule not loaded. Refresh page.')
        return
      }

      const result = classifyIntent(capsule, fields)
      console.log('Classification result:', result)

      if (!result) {
        console.error('ERROR: classifyIntent returned undefined')
        alert('ERROR: Classification failed. Check console.')
        return
      }

      setClassification(result)
      setSubmitting(true)

      const intentId = `intent-${Date.now()}`
      console.log('Submitting intent:', intentId)

      setTimeout(() => {
        try {
          submitIntent(intentId, fields)
          dispatchClassify({ ...result, intentId })
          console.log('Intent submitted successfully')
          setSubmitting(false)
        } catch (innerErr) {
          console.error('ERROR in submitIntent:', innerErr)
          alert(`ERROR: ${innerErr.message}`)
          setSubmitting(false)
        }
      }, 300)
    } catch (err) {
      console.error('ERROR in handleSubmit:', err)
      alert(`ERROR: ${err.message}`)
      setSubmitting(false)
    }
  }

  const requiredFields = capsule?.intentFields?.filter(f => f.required) || []
  const filledFields = requiredFields.filter(f => fields[f.name])
  const completionPercent = requiredFields.length > 0 ? (filledFields.length / requiredFields.length) * 100 : 0

  const canSubmit = capsule?.intentFields?.every(f => !f.required || fields[f.name]) && !submitting

  const displayClassification = classification || previewClassification
  const severityColor = displayClassification?.highestSeverity === 'block'
    ? '#dd0000'
    : displayClassification?.highestSeverity === 'warn'
      ? '#ff8800'
      : '#00aa00'

  const intentName = capsule?.domain === 'banking'
    ? `Treasury: ${fields.counterparty || '...'} / €${fields.amount_eur || 0}`
    : capsule?.domain === 'hospitality'
      ? `Guest: ${fields.guestName || '...'} / ${fields.dataCategory || '...'}`
      : 'Unnamed Intent'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '16px', background: '#ffffff', height: '100%', overflowY: 'auto' }}>
      {/* Status Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px', background: '#f0f0f0', borderRadius: '4px' }}>
        <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#333' }}>Intent Status:</span>
        <Tag intent={classification ? (classification.highestSeverity === 'block' ? Intent.DANGER : Intent.WARNING) : Intent.NONE} minimal>
          {classification ? (classification.highestSeverity === 'block' ? '🔴 HIGH-RISK' : classification.highestSeverity === 'warn' ? '🟡 WARNING' : '🟢 CLEAR') : '⚪ PENDING'}
        </Tag>
      </div>

      {/* Capsule Selector with Icon */}
      <Card style={{ marginBottom: '8px', padding: '12px' }}>
        <H4 style={{ margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>Governance Framework</span>
          <span style={{ fontSize: '16px' }}>{state.capsuleId === 'treasuryBaselIII' ? '💳' : '🏨'}</span>
        </H4>
        <HTMLSelect
          value={state.capsuleId}
          onChange={handleCapsuleChange}
          style={{ width: '100%', padding: '8px', fontSize: '13px', borderRadius: '4px' }}
        >
          <option value="hospitalityAnnexIII">🏨 KARP Hotel (EU AI Act Annex III)</option>
          <option value="treasuryBaselIII">💳 UniCredit Treasury (Basel III / CAR)</option>
        </HTMLSelect>
        <div style={{ fontSize: '11px', color: '#666666', marginTop: '10px', lineHeight: '1.5', padding: '8px', background: '#f5f5f5', borderRadius: '3px' }}>
          {capsule?.domain === 'hospitality' && '🔐 Guest data processing. Article 14 requires explicit human oversight before high-risk decisions (credit, PII).'}
          {capsule?.domain === 'banking' && '💰 Treasury operations. Basel III enforces real-time capital adequacy monitoring with fail-closed gates.'}
        </div>
      </Card>

      {/* Intent Form with Live Preview */}
      <Card style={{ padding: '12px' }}>
        <H4 style={{ margin: '0 0 12px 0' }}>Submit Intent</H4>

        {/* Completion Progress */}
        <div style={{ marginBottom: '12px' }}>
          <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#666', marginBottom: '6px' }}>
            Required Fields: {filledFields.length}/{requiredFields.length}
          </div>
          <ProgressBar value={completionPercent / 100} intent={completionPercent === 100 ? 'success' : 'primary'} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {capsule?.intentFields?.map(field => {
            const filled = fields[field.name]
            const isFocused = focusedField === field.name

            return (
              <div key={field.name} style={{
                padding: '10px',
                borderRadius: '4px',
                background: isFocused ? '#f0f8ff' : '#ffffff',
                border: isFocused ? '1px solid #0066cc' : '1px solid #e0e0e0',
                transition: 'all 0.2s ease'
              }}>
                <FormGroup
                  label={field.label}
                  labelInfo={field.required ? '(required)' : '(optional)'}
                  style={{ marginBottom: '0' }}
                >
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    {field.type === 'select' ? (
                      <HTMLSelect
                        value={fields[field.name] || ''}
                        onChange={(e) => handleFieldChange(field.name, e.target.value)}
                        onFocus={() => setFocusedField(field.name)}
                        onBlur={() => setFocusedField(null)}
                        disabled={submitting}
                        style={{ flex: 1 }}
                      >
                        <option value="">— Select —</option>
                        {field.options?.map(opt => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </HTMLSelect>
                    ) : field.type === 'number' ? (
                      <InputGroup
                        type="number"
                        value={fields[field.name] || ''}
                        onChange={(e) => handleFieldChange(field.name, e.target.value)}
                        onFocus={() => setFocusedField(field.name)}
                        onBlur={() => setFocusedField(null)}
                        disabled={submitting}
                        placeholder={`Enter ${field.label.toLowerCase()}`}
                        style={{ flex: 1 }}
                      />
                    ) : (
                      <InputGroup
                        type="text"
                        value={fields[field.name] || ''}
                        onChange={(e) => handleFieldChange(field.name, e.target.value)}
                        onFocus={() => setFocusedField(field.name)}
                        onBlur={() => setFocusedField(null)}
                        disabled={submitting}
                        placeholder={`Enter ${field.label.toLowerCase()}`}
                        style={{ flex: 1 }}
                      />
                    )}
                    {filled && <span style={{ color: '#00aa00', fontSize: '14px' }}>✓</span>}
                  </div>
                </FormGroup>
              </div>
            )
          })}
        </div>
      </Card>

      {/* Real-Time Risk Preview */}
      {previewClassification && !classification && (
        <Card
          style={{
            background: `${severityColor}11`,
            border: `2px dashed ${severityColor}`,
            padding: '12px',
            animation: 'pulse 2s infinite'
          }}
        >
          <div style={{ fontSize: '11px', fontWeight: 'bold', color: severityColor, marginBottom: '6px' }}>
            📊 LIVE RISK PREVIEW
          </div>
          <div style={{ fontSize: '12px', fontWeight: '600', color: severityColor }}>
            {previewClassification.badgeLabel}
          </div>
          {previewClassification.matchedRules.length > 0 && (
            <div style={{ fontSize: '10px', color: '#333333', marginTop: '8px' }}>
              <strong>Rules triggered:</strong>
              {previewClassification.matchedRules.slice(0, 2).map((rule, i) => (
                <div key={i} style={{ marginTop: '3px', marginLeft: '4px' }}>→ {rule.classification.substring(0, 50)}...</div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Classification Result (Final) */}
      {classification && (
        <Card
          style={{
            background: `${severityColor}22`,
            border: `2px solid ${severityColor}`,
            padding: '12px',
            animation: 'slideDown 0.3s ease'
          }}
        >
          <div style={{ fontSize: '12px', fontWeight: 'bold', color: severityColor, marginBottom: '8px' }}>
            {classification.highestSeverity === 'block' && '🔴 RISK CLASSIFICATION: HIGH-RISK'}
            {classification.highestSeverity === 'warn' && '🟡 RISK CLASSIFICATION: WARNING'}
            {classification.highestSeverity === 'none' && '🟢 CLASSIFICATION: APPROVED'}
          </div>
          <div style={{ fontSize: '13px', fontWeight: '600', color: severityColor, marginBottom: '8px' }}>
            {classification.badgeLabel}
          </div>
          {classification.matchedRules.length > 0 && (
            <div style={{ fontSize: '11px', color: '#333333', lineHeight: '1.6' }}>
              <strong>Triggered Rules ({classification.matchedRules.length}):</strong>
              {classification.matchedRules.map((rule, i) => (
                <div key={i} style={{ marginTop: '5px', paddingLeft: '10px', borderLeft: `2px solid ${severityColor}` }}>
                  <strong>{rule.classification}</strong>
                  <div style={{ fontSize: '10px', color: '#666', marginTop: '2px' }}>{rule.citation}</div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Submit Button */}
      <Button
        text={submitting ? '⏳ Submitting to Work Surface...' : '🚀 Send to Work Surface →'}
        intent={classification?.highestSeverity === 'block' ? 'danger' : 'primary'}
        fill
        large
        onClick={handleSubmit}
        disabled={!canSubmit}
        style={{ fontWeight: 'bold', fontSize: '14px' }}
      />
      {!canSubmit && (
        <div style={{ fontSize: '12px', color: '#dd0000', marginTop: '8px', padding: '8px', background: '#fff0f0', borderRadius: '4px' }}>
          ⚠️ Fill all required fields to submit
        </div>
      )}

      {classification?.highestSeverity === 'block' && (
        <div style={{ fontSize: '12px', color: '#dd0000', lineHeight: '1.6', padding: '10px', background: '#fff0f0', borderRadius: '4px', border: '1px solid #ffcccc' }}>
          ⚠️ <strong>HIGH-RISK DETECTED</strong><br/>
          This intent will be held at a pre-execution veto gate. The CRO must authorize with an Ed25519 signature before it proceeds.
        </div>
      )}

      {/* Intent Summary */}
      {Object.keys(fields).length > 0 && (
        <div style={{ fontSize: '11px', color: '#666', padding: '8px', background: '#f9f9f9', borderRadius: '3px', borderLeft: '3px solid #0066cc' }}>
          <strong>Intent:</strong> {intentName}
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
        @keyframes slideDown {
          from { transform: translateY(-10px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `}</style>
    </div>
  )
}
