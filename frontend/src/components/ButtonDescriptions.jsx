// Button Input/Output Schema Documentation
// Shows what happens when user clicks each button

export const BUTTON_SCHEMAS = {
  // SYSTEM STATUS SECTION
  'check-status': {
    name: 'Check Status',
    icon: '✓',
    description: 'Verify service is online',
    input: {
      servicePort: 'number (e.g., 8080)',
      serviceUrl: 'string (e.g., "http://localhost:8080")',
      endpoint: 'string (e.g., "/api/pool/status")'
    },
    process: [
      '1. Send GET request to URL + endpoint',
      '2. Wait for response (timeout 5 seconds)',
      '3. Check HTTP status code',
      '4. Parse JSON response'
    ],
    output: {
      status: 'enum: "✅ RUNNING" | "❌ NOT RESPONDING" | "❌ OFFLINE"',
      code: 'number (200 = success, other = error)',
      message: 'string (error message if failed)',
      timestamp: 'ISO string (when check happened)'
    },
    example: {
      input: { port: 8080, url: 'http://localhost:8080', endpoint: '/api/pool/status' },
      output: { status: '✅ RUNNING', code: 200, timestamp: '2026-09-01T12:48:55Z' }
    }
  },

  'start-service': {
    name: 'Start Service',
    icon: '▶',
    description: 'Copy command to start service in terminal',
    input: {
      serviceName: 'string (e.g., "Sandbox Pool Manager")',
      startCommand: 'string (bash command)'
    },
    process: [
      '1. Copy command text to clipboard',
      '2. Show alert confirming copy',
      '3. User pastes in terminal window',
      '4. User presses Enter to execute',
      '5. Service starts (takes 5-30 seconds)'
    ],
    output: {
      clipboardContents: 'string (bash command)',
      userAction: 'enum: "PASTED" | "DISCARDED"',
      serviceStatus: 'enum: "STARTING" | "RUNNING" | "FAILED"',
      logs: 'string (service startup output)'
    },
    example: {
      input: {
        serviceName: 'Sandbox Pool',
        startCommand: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml up -d sandbox-pool'
      },
      output: {
        clipboardContents: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml up -d sandbox-pool',
        userAction: 'PASTED',
        serviceStatus: 'RUNNING',
        logs: 'sandbox-pool is running'
      }
    }
  },

  'stop-service': {
    name: 'Stop Service',
    icon: '⏹',
    description: 'Copy command to stop service in terminal',
    input: {
      serviceName: 'string (e.g., "Prometheus")',
      stopCommand: 'string (bash command)'
    },
    process: [
      '1. Copy stop command to clipboard',
      '2. Warn: service will be unavailable',
      '3. Show alert with command',
      '4. User pastes in terminal',
      '5. User presses Enter',
      '6. Service stops (instant to 5 seconds)'
    ],
    output: {
      clipboardContents: 'string (bash command)',
      userAction: 'enum: "PASTED" | "DISCARDED"',
      serviceStatus: 'enum: "STOPPING" | "STOPPED" | "FAILED"',
      downtime: 'boolean (service unavailable)'
    },
    example: {
      input: {
        serviceName: 'Prometheus',
        stopCommand: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml stop prometheus'
      },
      output: {
        clipboardContents: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml stop prometheus',
        userAction: 'PASTED',
        serviceStatus: 'STOPPED',
        downtime: true
      }
    }
  },

  'copy-url': {
    name: 'Copy URL',
    icon: '📋',
    description: 'Copy service URL to clipboard',
    input: {
      serviceUrl: 'string (e.g., "http://localhost:8080")',
      endpoint: 'string (optional path, e.g., "/api/status")'
    },
    process: [
      '1. Combine URL + endpoint',
      '2. Copy full URL to clipboard',
      '3. Show success confirmation',
      '4. User can paste in browser address bar'
    ],
    output: {
      clipboardContents: 'string (full URL: "http://localhost:8080/api/status")',
      userAction: 'enum: "PASTED_TO_BROWSER" | "DISCARDED"',
      pageLoaded: 'boolean (if user opened in browser)'
    },
    example: {
      input: {
        serviceUrl: 'http://localhost:8080',
        endpoint: '/api/pool/status'
      },
      output: {
        clipboardContents: 'http://localhost:8080/api/pool/status',
        userAction: 'PASTED_TO_BROWSER',
        pageLoaded: true
      }
    }
  },

  'open-browser': {
    name: 'Open in Browser',
    icon: '🔗',
    description: 'Open service URL directly in new browser tab',
    input: {
      serviceUrl: 'string (full URL)',
      target: 'string (always "_blank" for new tab)'
    },
    process: [
      '1. Construct full URL from service + endpoint',
      '2. Open new browser tab/window',
      '3. Load URL',
      '4. Browser displays service interface or JSON response'
    ],
    output: {
      newTabOpened: 'boolean (true)',
      pageContent: 'string | object (HTML page or JSON)',
      statusCode: 'number (200 = success)',
      loadTime: 'number (milliseconds to load)'
    },
    example: {
      input: {
        serviceUrl: 'http://localhost:3001',
        target: '_blank'
      },
      output: {
        newTabOpened: true,
        pageContent: 'Grafana dashboard HTML',
        statusCode: 200,
        loadTime: 342
      }
    }
  },

  // TRANSACTION SIMULATOR
  'start-simulation': {
    name: 'Start Transaction Flow',
    icon: '▶',
    description: 'Run 8-step hotel booking simulation',
    input: {
      guestName: 'string (e.g., "Elena Kováčová")',
      amount: 'number (€, e.g., 450)',
      paymentMethod: 'enum: "card" | "bank" | "cash"'
    },
    process: [
      '1. Validate inputs (amount > 0)',
      '2. Step 1: Create booking request',
      '3. Step 2: Load guest history (2 sec)',
      '4. Step 3: Evaluate risk model (2 sec)',
      '5. Step 4: Compliance check (2 sec)',
      '6. Step 5: Gate decision - HALT (2 sec)',
      '7. Step 6: Human review (2 sec)',
      '8. Step 7: Sign proof (2 sec)',
      '9. Step 8: Authorization result (2 sec)'
    ],
    output: {
      bookingId: 'string (unique ID)',
      guestName: 'string',
      amount: 'number (€)',
      steps: 'array of step statuses',
      gateDecision: 'enum: "APPROVED" | "HALTED" | "REJECTED"',
      proofSignature: 'string (Ed25519: xxxxxxxx)',
      totalTime: 'number (milliseconds)',
      ledgerEntry: 'object (added to proof ledger)'
    },
    example: {
      input: {
        guestName: 'Elena Kováčová',
        amount: 450,
        paymentMethod: 'card'
      },
      output: {
        bookingId: 'BOOKING-2026-09-01-001',
        guestName: 'Elena Kováčová',
        amount: 450,
        steps: [
          { step: 1, status: 'complete', duration: 100 },
          { step: 2, status: 'complete', duration: 2000 },
          { step: 3, status: 'complete', duration: 2000 },
          { step: 4, status: 'complete', duration: 2000 },
          { step: 5, status: 'halt', duration: 2000, reason: 'EU_AI_ACT_PII_CHECK' },
          { step: 6, status: 'complete', duration: 2000, decision: 'HUMAN_APPROVED' },
          { step: 7, status: 'complete', duration: 2000 },
          { step: 8, status: 'complete', duration: 2000, result: 'APPROVED' }
        ],
        gateDecision: 'HALTED_AT_STEP_5',
        proofSignature: 'ed25519:3f8c5a2d1e9b4a7c6f0e3d8a1b9c7e5f',
        totalTime: 16100,
        ledgerEntry: {
          timestamp: '2026-09-01T12:48:55.087Z',
          action: 'booking.complete',
          cost: '€0.000024',
          signature: 'ed25519:...'
        }
      }
    }
  },

  // DAG NAVIGATION
  'pause-resume': {
    name: 'Pause/Resume DAG',
    icon: '⏸/▶',
    description: 'Pause or resume agent execution flow animation',
    input: {
      currentState: 'enum: "RUNNING" | "PAUSED"',
      currentStep: 'number (1-5)'
    },
    process: [
      '1. Check current state',
      '2. If RUNNING: Stop animation timer',
      '3. If PAUSED: Restart animation timer',
      '4. Update UI button text'
    ],
    output: {
      newState: 'enum: "RUNNING" | "PAUSED"',
      currentStep: 'number (unchanged)',
      stepDuration: 'number (3000ms at 1x speed)',
      buttonText: 'string ("⏸ Pause" or "▶ Resume")'
    },
    example: {
      input: { currentState: 'RUNNING', currentStep: 3 },
      output: { newState: 'PAUSED', currentStep: 3, stepDuration: 3000, buttonText: '▶ Resume' }
    }
  },

  'previous-next-step': {
    name: 'Previous/Next Step',
    icon: '◀/▶',
    description: 'Navigate backward or forward through execution steps',
    input: {
      direction: 'enum: "PREVIOUS" | "NEXT"',
      currentStep: 'number (0-5)',
      totalSteps: 'number (5)'
    },
    process: [
      '1. Check direction',
      '2. If PREVIOUS: currentStep = max(0, currentStep - 1)',
      '3. If NEXT: currentStep = min(5, currentStep + 1)',
      '4. Update SVG visualization',
      '5. Update progress bar'
    ],
    output: {
      newStep: 'number (0-5)',
      progress: 'string ("2 / 5")',
      nodeStates: 'array of enum ("complete" | "running" | "idle" | "halt")',
      canGoBack: 'boolean',
      canGoForward: 'boolean'
    },
    example: {
      input: { direction: 'NEXT', currentStep: 2, totalSteps: 5 },
      output: {
        newStep: 3,
        progress: '3 / 5',
        nodeStates: ['complete', 'complete', 'complete', 'running', 'idle'],
        canGoBack: true,
        canGoForward: true
      }
    }
  },

  'set-speed': {
    name: 'Set Animation Speed',
    icon: '⚡',
    description: 'Change DAG animation speed (0.5x, 1x, 2x)',
    input: {
      speed: 'enum: 0.5 | 1 | 2',
      baseDuration: 'number (3000ms)'
    },
    process: [
      '1. Calculate actual duration: baseDuration / speed',
      '2. Update animation timer interval',
      '3. Re-render progress'
    ],
    output: {
      speed: 'enum: 0.5 | 1 | 2',
      stepDuration: 'number (ms per step)',
      totalFlowTime: 'number (ms for all 5 steps)',
      buttonHighlighted: 'enum: "0.5x" | "1x" | "2x"'
    },
    example: {
      input: { speed: 0.5, baseDuration: 3000 },
      output: {
        speed: 0.5,
        stepDuration: 6000,
        totalFlowTime: 30000,
        buttonHighlighted: '0.5x'
      }
    }
  },

  // COMPLIANCE REPORTS
  'generate-report': {
    name: 'Generate Report',
    icon: '📄',
    description: 'Generate compliance report for selected regulator',
    input: {
      reportType: 'enum: "eu-ai-act" | "cac-30" | "gdpr" | "soc2"',
      reportData: 'object (populated from system state)'
    },
    process: [
      '1. Load report template',
      '2. Fill in sections with SMAOS data',
      '3. Add timestamps',
      '4. Format for readability',
      '5. Display in UI'
    ],
    output: {
      reportType: 'string',
      sections: 'array of { title, content }',
      generatedAt: 'ISO string',
      pageCount: 'number',
      status: 'string ("Ready for submission")'
    },
    example: {
      input: { reportType: 'eu-ai-act' },
      output: {
        reportType: 'EU AI Act Compliance Report',
        sections: [
          { title: 'EXECUTIVE SUMMARY', content: '...' },
          { title: 'RISK CLASSIFICATION', content: '...' },
          { title: 'HUMAN OVERSIGHT', content: '...' }
        ],
        generatedAt: '2026-09-01T12:48:55Z',
        pageCount: 8,
        status: '✅ REPORT GENERATED & READY FOR SUBMISSION'
      }
    }
  },

  'download-pdf': {
    name: 'Download PDF',
    icon: '📥',
    description: 'Download generated report as PDF file',
    input: {
      reportData: 'object (generated report)',
      reportType: 'string (e.g., "EU AI Act")'
    },
    process: [
      '1. Generate PDF from report data',
      '2. Add headers, footers, page numbers',
      '3. Create blob from PDF bytes',
      '4. Trigger browser download',
      '5. Show success message'
    ],
    output: {
      filename: 'string (e.g., "SMAOS-EU-AI-Act-2026-09-01.pdf")',
      fileSize: 'number (bytes)',
      downloaded: 'boolean',
      location: 'string (browser default: ~/Downloads/)'
    },
    example: {
      input: {
        reportData: { /* full report */ },
        reportType: 'EU AI Act'
      },
      output: {
        filename: 'SMAOS-EU-AI-Act-2026-09-01.pdf',
        fileSize: 245632,
        downloaded: true,
        location: '~/Downloads/SMAOS-EU-AI-Act-2026-09-01.pdf'
      }
    }
  }
}

// Helper component to show button descriptions
export function ButtonHelpTooltip({ buttonKey }) {
  const schema = BUTTON_SCHEMAS[buttonKey]
  if (!schema) return null

  return (
    <div style={{
      position: 'absolute',
      background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.25) 0%, rgba(59, 130, 246, 0.1) 100%)',
      border: '2px solid #3b82f6',
      borderRadius: '10px',
      padding: '12px 14px',
      fontSize: '10px',
      color: '#a0a0a0',
      maxWidth: '320px',
      lineHeight: '1.5',
      zIndex: 100,
      whiteSpace: 'normal'
    }}>
      <div style={{ fontWeight: 'bold', color: '#3b82f6', marginBottom: '6px' }}>
        {schema.icon} {schema.name}
      </div>
      <div style={{ marginBottom: '8px' }}>
        {schema.description}
      </div>
      <div style={{ borderTop: '1px solid rgba(59, 130, 246, 0.3)', paddingTop: '6px' }}>
        <div style={{ fontWeight: 'bold', color: '#3b82f6', marginBottom: '4px' }}>INPUT:</div>
        <div>{Object.entries(schema.input).map(([k, v]) => `${k}: ${v}`).join(', ')}</div>
      </div>
      <div style={{ borderTop: '1px solid rgba(59, 130, 246, 0.3)', paddingTop: '6px', marginTop: '6px' }}>
        <div style={{ fontWeight: 'bold', color: '#10b981', marginBottom: '4px' }}>OUTPUT:</div>
        <div>{Object.entries(schema.output).map(([k, v]) => `${k}: ${v}`).join(', ')}</div>
      </div>
    </div>
  )
}
