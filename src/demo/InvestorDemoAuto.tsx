/**
 * SMAOS Osiris — Investor Demo Auto-Play Mode
 * Hands-off 10-minute demo with replay, slow-motion, and narration
 */

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

interface DemoStep {
  id: string;
  title: string;
  description: string;
  duration: number; // milliseconds
  action: () => void;
  highlight?: string;
}

const demoSteps: DemoStep[] = [
  {
    id: 'intro',
    title: 'The Black Box',
    description: 'This is not ChatGPT. This is an operational governance engine.',
    duration: 5000,
    action: () => console.log('Intro'),
    highlight: 'header'
  },
  {
    id: 'pilot-status',
    title: 'Three Pilots Running',
    description: 'Hotel credit scoring, glass factory safety, school access control. All processing decisions live.',
    duration: 6000,
    action: () => console.log('Showing pilots'),
    highlight: 'panel-canvas'
  },
  {
    id: 'boundary-hit',
    title: 'Policy Boundary Triggered',
    description: 'Agent proposed a high-risk credit decision. The system detected Annex III boundary.',
    duration: 4000,
    action: () => console.log('Boundary triggered'),
    highlight: 'node-policy'
  },
  {
    id: 'veto-gate-open',
    title: 'Fail-Closed Execution Halted',
    description: 'Execution PAUSES. The system does not decide for humans. It waits for governance.',
    duration: 5000,
    action: () => console.log('Veto gate appears'),
    highlight: 'veto-modal'
  },
  {
    id: 'approval-shown',
    title: 'Human Veto Gate Visible',
    description: 'What the agent wanted. What rule it checked. Which alternatives it rejected.',
    duration: 5000,
    action: () => console.log('Showing approval details'),
    highlight: 'veto-details'
  },
  {
    id: 'sign-decision',
    title: 'Cryptographic Approval',
    description: 'The evaluator signs with Ed25519. Governance is not a suggestion; it\'s mathematically enforced.',
    duration: 6000,
    action: () => console.log('Signature approved'),
    highlight: 'signature-button'
  },
  {
    id: 'execution-resumes',
    title: 'Execution Resumes',
    description: 'Decision is captured in agentacct. Work receipt is finalized with cost and approval metadata.',
    duration: 5000,
    action: () => console.log('Resume execution'),
    highlight: 'receipt-captured'
  },
  {
    id: 'proof-gallery',
    title: 'Seven Independent Proofs',
    description: 'CanIRun: Local GPU. FreeToken: 39.3 tok/s. agentacct: Work receipt. unlazy: Gate verification. Is Agentic: A+ rating. RAGAS: 87% accuracy. AP2: Immutable ledger.',
    duration: 10000,
    action: () => console.log('Showing proofs'),
    highlight: 'proof-gallery'
  },
  {
    id: 'air-gap-moment',
    title: 'The Air-Gap Proof',
    description: 'We\'re now unplugging the internet. Watch: everything still works. Zero cloud calls. Zero data exfiltration.',
    duration: 8000,
    action: () => console.log('Air-gap demo'),
    highlight: 'air-gap-indicator'
  },
  {
    id: 'git-anchor',
    title: 'Immutable Public Ledger',
    description: 'We plug back in. Git commits push to public blockchain. Ed25519 PQC signatures prove history cannot be altered.',
    duration: 7000,
    action: () => console.log('Git commits'),
    highlight: 'git-commits'
  },
  {
    id: 'closing',
    title: 'Governance Made Visible',
    description: 'Every decision is auditable. Every claim is cryptographically verified. No black box.',
    duration: 8000,
    action: () => console.log('Closing'),
    highlight: 'header'
  }
];

export const InvestorDemoAuto: React.FC = () => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [speed, setSpeed] = useState(1); // 1 = normal, 0.5 = slow-motion, 2 = fast
  const [highlightedElement, setHighlightedElement] = useState<string | null>(null);

  const currentStep = demoSteps[currentStepIndex];

  // Auto-advance steps
  useEffect(() => {
    if (!isPlaying) return;

    const duration = currentStep.duration / speed;
    const timer = setTimeout(() => {
      if (currentStepIndex < demoSteps.length - 1) {
        setCurrentStepIndex(currentStepIndex + 1);
      } else {
        setIsPlaying(false); // Demo ends
      }
    }, duration);

    return () => clearTimeout(timer);
  }, [isPlaying, currentStepIndex, speed]);

  const handlePlay = () => setIsPlaying(true);
  const handlePause = () => setIsPlaying(false);
  const handleReplay = () => {
    setCurrentStepIndex(0);
    setIsPlaying(true);
  };
  const handleNext = () => {
    if (currentStepIndex < demoSteps.length - 1) {
      setCurrentStepIndex(currentStepIndex + 1);
    }
  };
  const handlePrevious = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(currentStepIndex - 1);
    }
  };

  return (
    <motion.div
      className="investor-demo"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      {/* Narration Card */}
      <motion.div
        className="demo-narration glass-panel"
        key={currentStep.id}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <h2>{currentStep.title}</h2>
        <p className="narration-text">{currentStep.description}</p>

        {/* Progress bar */}
        <div className="progress-container">
          <div className="progress-bar">
            <motion.div
              className="progress-fill"
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{
                duration: currentStep.duration / 1000 / speed,
                ease: 'linear'
              }}
            />
          </div>
          <span className="step-counter">
            Step {currentStepIndex + 1} of {demoSteps.length}
          </span>
        </div>
      </motion.div>

      {/* Controls */}
      <div className="demo-controls glass-panel">
        <button
          className="btn btn-primary"
          onClick={handlePlay}
          disabled={isPlaying}
        >
          ▶ Play
        </button>
        <button
          className="btn"
          onClick={handlePause}
          disabled={!isPlaying}
        >
          ⏸ Pause
        </button>
        <button className="btn" onClick={handlePrevious}>
          ⏮ Previous
        </button>
        <button className="btn" onClick={handleNext}>
          Next ⏭
        </button>
        <button className="btn" onClick={handleReplay}>
          🔄 Replay
        </button>

        {/* Speed control */}
        <div className="speed-control">
          <label>Speed:</label>
          <select
            value={speed}
            onChange={(e) => setSpeed(parseFloat(e.target.value))}
            disabled={isPlaying}
          >
            <option value={0.5}>Slow (0.5×)</option>
            <option value={1}>Normal (1×)</option>
            <option value={1.5}>Fast (1.5×)</option>
            <option value={2}>Very Fast (2×)</option>
          </select>
        </div>
      </div>

      {/* Highlight overlay */}
      {currentStep.highlight && (
        <motion.div
          className="highlight-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.2 }}
          transition={{ duration: 0.3 }}
          style={{
            pointerEvents: 'none'
          }}
        >
          <style>{`
            #${currentStep.highlight} {
              box-shadow: 0 0 30px rgba(16, 185, 129, 0.6) !important;
              border-color: var(--color-emerald-500) !important;
            }
          `}</style>
        </motion.div>
      )}

      <style>{`
        .investor-demo {
          display: flex;
          flex-direction: column;
          gap: var(--spacing-lg);
          padding: var(--spacing-xl);
          height: 100vh;
          background: linear-gradient(135deg, var(--color-bg-primary) 0%, var(--color-bg-tertiary) 100%);
        }

        .demo-narration {
          flex: 1;
          display: flex;
          flex-direction: column;
          justify-content: center;
          padding: var(--spacing-xl);
          text-align: center;
        }

        .demo-narration h2 {
          margin-bottom: var(--spacing-lg);
          background: linear-gradient(135deg, var(--color-emerald-400), var(--color-amber-400));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .narration-text {
          font-size: 18px;
          line-height: 1.8;
          color: var(--color-text-secondary);
          margin-bottom: var(--spacing-xl);
        }

        .progress-container {
          display: flex;
          flex-direction: column;
          gap: var(--spacing-md);
        }

        .progress-bar {
          height: 4px;
          background: var(--color-bg-tertiary);
          border-radius: 2px;
          overflow: hidden;
        }

        .progress-fill {
          height: 100%;
          background: linear-gradient(90deg, var(--color-emerald-500), var(--color-amber-500));
          box-shadow: 0 0 12px var(--color-emerald-500);
          transform-origin: left;
        }

        .step-counter {
          font-size: 12px;
          color: var(--color-text-tertiary);
          text-transform: uppercase;
          letter-spacing: 1px;
        }

        .demo-controls {
          display: flex;
          gap: var(--spacing-md);
          align-items: center;
          flex-wrap: wrap;
          justify-content: center;
          padding: var(--spacing-lg);
        }

        .speed-control {
          display: flex;
          align-items: center;
          gap: var(--spacing-sm);
          margin-left: var(--spacing-lg);
        }

        .speed-control label {
          font-size: 12px;
          text-transform: uppercase;
          color: var(--color-text-tertiary);
        }

        .speed-control select {
          background: var(--color-bg-tertiary);
          color: var(--color-text-primary);
          border: 1px solid var(--color-border-secondary);
          padding: var(--spacing-sm);
          border-radius: var(--radius-md);
          cursor: pointer;
        }

        .btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .highlight-overlay {
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(0, 0, 0, 0.3);
          pointer-events: none;
          z-index: 1000;
        }
      `}</style>
    </motion.div>
  );
};

export default InvestorDemoAuto;
