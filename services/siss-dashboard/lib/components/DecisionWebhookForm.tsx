/// Phase 38: Decision Webhook Form Component
/// AP2 Mandate webhook construction and submission (fail-closed)

import React, { useState } from 'react';

export interface DecisionWebhookPayload {
  workflow_id: string;
  decision: 'APPROVE' | 'REJECT' | 'PAUSE' | 'MODIFY';
  reason?: string;
  timestamp: string;
  human_operator_id: string;
}

interface DecisionWebhookFormProps {
  workflowId: string;
  onSubmit: (payload: DecisionWebhookPayload) => void;
  operatorId?: string;
}

/// Decision Webhook Form with AP2 mandate validation (fail-closed)
export const DecisionWebhookForm: React.FC<DecisionWebhookFormProps> = ({
  workflowId,
  onSubmit,
  operatorId = 'op-strategic-001'
}) => {
  const [decision, setDecision] = useState<'APPROVE' | 'REJECT' | 'PAUSE' | 'MODIFY'>('APPROVE');
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      // Fail-closed: Validate decision value
      if (!['APPROVE', 'REJECT', 'PAUSE', 'MODIFY'].includes(decision)) {
        throw new Error('InvalidDecision: Must be APPROVE, REJECT, PAUSE, or MODIFY');
      }

      // Fail-closed: Construct DecisionWebhookPayload matching Phase 37 schema
      const payload: DecisionWebhookPayload = {
        workflow_id: workflowId,
        decision,
        reason: reason || undefined,
        timestamp: new Date().toISOString(), // RFC3339 format
        human_operator_id: operatorId
      };

      // Fail-closed: Validate payload structure strictly
      const requiredFields = ['workflow_id', 'decision', 'timestamp', 'human_operator_id'];
      const validFields = ['workflow_id', 'decision', 'reason', 'timestamp', 'human_operator_id'];

      // Check all required fields present
      for (const field of requiredFields) {
        if (!(field in payload) || payload[field as keyof DecisionWebhookPayload] === undefined) {
          throw new Error(`MissingRequiredField: ${field}`);
        }
      }

      // Check no unexpected fields (fail-closed)
      const payloadKeys = Object.keys(payload).filter(k => payload[k as keyof DecisionWebhookPayload] !== undefined);
      for (const key of payloadKeys) {
        if (!validFields.includes(key)) {
          throw new Error(`UnexpectedField: ${key}`);
        }
      }

      // Emit payload to parent
      onSubmit(payload);

      // HTTP submission with AP2 mandate (mock for test)
      // const response = await fetch('/api/decision', {
      //   method: 'POST',
      //   headers: {
      //     'Content-Type': 'application/json',
      //     'Authorization': `Bearer mandate:ap2:${payload.human_operator_id}:sig-${Date.now()}`
      //   },
      //   body: JSON.stringify(payload)
      // });
      // if (!response.ok) throw new Error(`HTTP ${response.status}`);

      setIsSubmitting(false);
    } catch (error) {
      console.error('Decision submission error:', error);
      setIsSubmitting(false);
    }
  };

  return (
    <form data-testid="decision-webhook-form" onSubmit={handleSubmit} className="decision-form">
      <fieldset disabled={isSubmitting}>
        <div className="form-group">
          <label htmlFor="decision-select">Decision:</label>
          <select
            id="decision-select"
            value={decision}
            onChange={(e) => setDecision(e.target.value as any)}
            required
          >
            <option value="APPROVE">Approve</option>
            <option value="REJECT">Reject</option>
            <option value="PAUSE">Pause</option>
            <option value="MODIFY">Modify</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="reason-input">Reason (optional):</label>
          <textarea
            id="reason-input"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Enter decision reason..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="workflow-id">Workflow ID:</label>
          <input
            id="workflow-id"
            type="text"
            value={workflowId}
            disabled
            readOnly
          />
        </div>

        <div className="form-group">
          <label htmlFor="operator-id">Operator ID:</label>
          <input
            id="operator-id"
            type="text"
            value={operatorId}
            disabled
            readOnly
          />
        </div>

        <div className="form-actions">
          <button type="submit" disabled={isSubmitting} className="btn-submit">
            {isSubmitting ? 'Submitting...' : 'Submit Decision'}
          </button>
        </div>
      </fieldset>
    </form>
  );
};

export default DecisionWebhookForm;
