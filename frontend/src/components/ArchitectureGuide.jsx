import { useState } from 'react'

export default function ArchitectureGuide() {
  const [expandedSection, setExpandedSection] = useState('overview')

  const Section = ({ id, title, icon, description }) => (
    <div style={{
      background: expandedSection === id
        ? 'linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(59, 130, 246, 0.05) 100%)'
        : 'rgba(26, 31, 58, 0.4)',
      border: expandedSection === id ? '2px solid #3b82f6' : '1px solid rgba(100, 116, 139, 0.3)',
      borderRadius: '12px',
      padding: '14px',
      marginBottom: '12px',
      cursor: 'pointer',
      transition: 'all 0.3s ease',
      backdropFilter: 'blur(8px)'
    }}
    onClick={() => setExpandedSection(expandedSection === id ? null : id)}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        marginBottom: expandedSection === id ? '12px' : '0'
      }}>
        <div style={{ fontSize: '24px' }}>{icon}</div>
        <div style={{
          fontSize: '12px',
          fontWeight: 'bold',
          color: '#3b82f6',
          flex: 1
        }}>
          {title}
        </div>
        <div style={{
          fontSize: '12px',
          color: '#a0a0a0',
          transition: 'transform 0.3s ease',
          transform: expandedSection === id ? 'rotate(180deg)' : 'rotate(0deg)'
        }}>
          ▼
        </div>
      </div>

      {expandedSection === id && (
        <div style={{
          fontSize: '11px',
          color: '#a0a0a0',
          lineHeight: '1.6',
          borderTop: '1px solid rgba(45, 55, 72, 0.3)',
          paddingTop: '12px'
        }}>
          {description}
        </div>
      )}
    </div>
  )

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
        📚 System Architecture Guide (Explained Simply)
      </div>

      {/* ========== SECTION 1: THE BIG PICTURE ========== */}
      <Section
        id="overview"
        icon="🎯"
        title="THE BIG PICTURE: What is SMAOS?"
        description={
          <>
            <strong>Imagine a hotel reception desk:</strong>
            <br/>
            A guest walks in and says, "I want to book a €450 room." The receptionist (= our AI agent) needs to:
            <br/>
            1. Check if the guest can pay (look up credit history)
            <br/>
            2. Make sure the decision is fair (check the credit model)
            <br/>
            3. Keep the guest's information safe (don't expose credit card number)
            <br/>
            4. Write down what happened (keep a record for auditors)
            <br/>
            <br/>
            <strong>The problem:</strong> Regular AI systems (ChatGPT, Claude, etc.) can expose private data or make unfair decisions without checking.
            <br/>
            <strong>Our solution:</strong> SMAOS puts "guards" (compliance gates) at every step to catch mistakes BEFORE they happen.
            <br/>
            <strong>Result:</strong> 100% compliant with EU AI Act, zero risk of data leaks, perfect audit trail.
          </>
        }
      />

      {/* ========== SECTION 2: CONTAINERS ========== */}
      <Section
        id="containers"
        icon="📦"
        title="CONTAINERS: The Isolation Boxes"
        description={
          <>
            <strong>Toyota Manufacturing Analogy:</strong>
            <br/>
            In a Toyota factory, each robot arm has its own workspace with walls. Why?
            <br/>
            • If robot #1 makes a mistake, it doesn't crash robot #2
            <br/>
            • You can replace robot #1 without affecting the others
            <br/>
            • Each robot can only access what's in its box
            <br/>
            <br/>
            <strong>Our containers are exactly the same:</strong>
            <br/>
            🐳 <strong>Container #1:</strong> Sandbox for Agent Task A (€450 booking)
            <br/>
            • Memory: 512MB (limited, can't use everything)
            <br/>
            • CPU: 50% quota (can't hog resources)
            <br/>
            • Network: NONE (can't call OpenAI, Azure, Google)
            <br/>
            • Lifespan: 60 minutes, then DESTROYED (like a disposable cup)
            <br/>
            <br/>
            🐳 <strong>Container #2:</strong> Sandbox for Agent Task B (€800 booking)
            <br/>
            • Same isolation, same limits
            <br/>
            • Task A data CANNOT leak into Task B
            <br/>
            <br/>
            <strong>Why this matters:</strong>
            <br/>
            ✅ Guest #1's credit card is in Container #1
            <br/>
            ✅ Guest #2's credit card is in Container #2
            <br/>
            ✅ Even if Container #1 crashes, Guest #2 is safe
            <br/>
            ✅ After 60 minutes, Container #1 is destroyed (no residual data)
          </>
        }
      />

      {/* ========== SECTION 3: SANDBOX POOL ========== */}
      <Section
        id="pool"
        icon="🏊"
        title="SANDBOX POOL: The Pre-Warmed Containers"
        description={
          <>
            <strong>Restaurant Kitchen Analogy:</strong>
            <br/>
            A good restaurant doesn't start cooking when you order. It keeps:
            <br/>
            • 2 clean plates ready (pre-washed)
            <br/>
            • 2 pans heating on the stove (pre-warmed)
            <br/>
            • When you order, they grab a plate + pan immediately
            <br/>
            <br/>
            <strong>Our Sandbox Pool does the same:</strong>
            <br/>
            🎯 <strong>Pre-warmed containers:</strong>
            <br/>
            Container #1: ✓ Ready (Python loaded, imports cached)
            <br/>
            Container #2: ✓ Ready (Python loaded, imports cached)
            <br/>
            <br/>
            When a guest books a room:
            <br/>
            1. Agent requests a container: "I need a sandbox!"
            <br/>
            2. Pool manager: "Here, take Container #1" (instant)
            <br/>
            3. Agent runs the task inside (no startup delay)
            <br/>
            4. Agent finishes, releases Container #1
            <br/>
            5. Pool manager: "Destroy Container #1, create a new pre-warmed one"
            <br/>
            <br/>
            <strong>Why this matters:</strong>
            <br/>
            ✅ <strong>Speed:</strong> Agent gets a sandbox in 10ms (faster than calling OpenAI)
            <br/>
            ✅ <strong>Cost:</strong> No startup overhead (no Docker pull, no Python init)
            <br/>
            ✅ <strong>Safety:</strong> Fresh container = zero residual data from previous tasks
          </>
        }
      />

      {/* ========== SECTION 4: THE SERVERS ========== */}
      <Section
        id="servers"
        icon="🖥️"
        title="SERVERS: What's Actually Running (Right Now)"
        description={
          <>
            <strong>Hotel Concierge Desk Analogy:</strong>
            <br/>
            A hotel has:
            <br/>
            • Receptionist (books rooms, answers questions)
            <br/>
            • Manager (watches everything, keeps metrics)
            <br/>
            • Accountant (records costs, audits)
            <br/>
            <br/>
            <strong>Our servers do the same:</strong>
            <br/>
            <br/>
            🌐 <strong>Sandbox Pool Manager (Port 8080)</strong>
            <br/>
            Role: The receptionist
            <br/>
            Job: Lease/release containers, execute agent code
            <br/>
            Example: Agent says "Execute this Python code in a sandbox"
            <br/>
            → Pool Manager: "OK, here's Container #1, running..." → "Done! Cost €0.000008"
            <br/>
            <br/>
            📊 <strong>Prometheus (Port 9090)</strong>
            <br/>
            Role: The manager (watches the hotel)
            <br/>
            Job: Collect metrics every 15 seconds
            <br/>
            Example: "How many containers are running? What's the CPU load? Token speed?"
            <br/>
            → Records: "39.3 tok/s, 2 containers ready, 0 Kbps egress"
            <br/>
            <br/>
            📈 <strong>Grafana (Port 3001)</strong>
            <br/>
            Role: The visual dashboard
            <br/>
            Job: Shows beautiful charts of what Prometheus collected
            <br/>
            Example: Investor asks "Is the system healthy?"
            <br/>
            → You point to Grafana: "See? Green lines everywhere. 100% uptime."
            <br/>
            <br/>
            ⚡ <strong>Log Streamer (Port 8081)</strong>
            <br/>
            Role: The real-time speaker
            <br/>
            Job: Broadcast events live (SSE = Server-Sent Events)
            <br/>
            Example: "Container started... Agent requested PII... Gate blocked it... Proof signed"
            <br/>
            <br/>
            🎨 <strong>Osiris Cockpit (Port 5173)</strong>
            <br/>
            Role: The beautiful dashboard (what you're looking at now)
            <br/>
            Job: Show everything in real-time with animations
            <br/>
            Example: You enter €450, watch it flow through the system, see the gate halt it
          </>
        }
      />

      {/* ========== SECTION 5: THE DATABASE ========== */}
      <Section
        id="database"
        icon="💾"
        title="DATABASE (PostgreSQL): The Guest Records"
        description={
          <>
            <strong>Library Card System Analogy:</strong>
            <br/>
            A library keeps:
            <br/>
            • Who is registered (guests)
            <br/>
            • What books they borrowed (booking history)
            <br/>
            • When they borrowed them (timeline)
            <br/>
            • How much they owe (payment status)
            <br/>
            <br/>
            <strong>Our database stores:</strong>
            <br/>
            <br/>
            👤 <strong>Guest Records Table</strong>
            <br/>
            ID | Name | Email | Credit_Score | Payment_History | Risk_Level
            <br/>
            1 | Elena | elena@... | 750 | 12/12 on time | LOW
            <br/>
            2 | John | john@... | 680 | 10/12 late | MEDIUM
            <br/>
            3 | Maria | maria@... | 550 | 6/12 defaulted | HIGH
            <br/>
            <br/>
            📅 <strong>Booking History Table</strong>
            <br/>
            Guest_ID | Date | Amount | Status | Notes
            <br/>
            1 | Sep 1 | €450 | Approved | ✓ Signed proof
            <br/>
            2 | Aug 31 | €300 | Approved | ✓ Signed proof
            <br/>
            <br/>
            🔐 <strong>Proof Trail Table (agentacct ledger)</strong>
            <br/>
            Timestamp | Action | Cost | Ed25519_Sig | Merkle_Root
            <br/>
            11:28:55 | agent.plan | €0.000006 | ed25519:8j2ag... | git:05f0319d
            <br/>
            11:28:54 | gate.check | €0.000001 | ed25519:ugg73... | git:05f0319d
            <br/>
            <br/>
            <strong>Why this matters:</strong>
            <br/>
            ✅ <strong>Speed:</strong> Queries run in 10ms (pgvector indexing)
            <br/>
            ✅ <strong>Privacy:</strong> Credit card numbers are NEVER stored (only hashes)
            <br/>
            ✅ <strong>Audit:</strong> Every action logged with cryptographic proof
          </>
        }
      />

      {/* ========== SECTION 6: THE PILOT ========== */}
      <Section
        id="pilot"
        icon="🏨"
        title="THE PILOT: Hotel Credit Assessment (Real Example)"
        description={
          <>
            <strong>What happens when a guest books a €450 room:</strong>
            <br/>
            <br/>
            <strong>Step 1: The Request</strong>
            <br/>
            👤 Guest Elena: "I want to book the suite for €450"
            <br/>
            🏨 Receptionist (Osiris UI): [Click button] "Agent, assess this booking"
            <br/>
            <br/>
            <strong>Step 2: Agent Takes Over</strong>
            <br/>
            🤖 Agent: "OK, I need to check if Elena can pay"
            <br/>
            🤖 Agent: "Request a sandbox from the pool"
            <br/>
            🏊 Pool Manager: "Here's Container #1, you have 60 minutes"
            <br/>
            <br/>
            <strong>Step 3: Data Gathering (L2 Memory)</strong>
            <br/>
            🤖 Agent: "Query the database for Elena's history"
            <br/>
            💾 Database: "Elena has 12 successful bookings, credit score 750"
            <br/>
            🤖 Agent: "Good, she's low-risk"
            <br/>
            <br/>
            <strong>Step 4: Compliance Gate (L3 Permit)</strong>
            <br/>
            🤖 Agent: "I want to read Elena's credit card for verification"
            <br/>
            🔐 Gate: "WAIT! Is this allowed by EU AI Act?"
            <br/>
            🔐 Gate: "Reading unmasked PII requires human approval"
            <br/>
            🔐 Gate: "EXECUTION HALTED"
            <br/>
            <br/>
            <strong>Step 5: Human Review (You)</strong>
            <br/>
            🧑 You (hotel manager): "Why did it halt?"
            <br/>
            💬 System: "Agent wanted unmasked credit card. Not allowed without your approval."
            <br/>
            💬 System: "Alternatives: (1) Use masked card (last 4 digits), (2) Skip PII, (3) Get legal approval"
            <br/>
            🧑 You: "Use masked card instead"
            <br/>
            <br/>
            <strong>Step 6: Continue with Safe Path</strong>
            <br/>
            🤖 Agent: "OK, using masked card: ****-****-****-5678"
            <br/>
            🤖 Agent: "Elena's risk: LOW. Recommendation: APPROVE"
            <br/>
            <br/>
            <strong>Step 7: Proof Generation (L8 Proof)</strong>
            <br/>
            ✍️ System: "Signing the decision with Ed25519 key"
            <br/>
            ✍️ System: "Recording in immutable ledger"
            <br/>
            📜 Ledger: timestamp=11:28:55 | action=gate.allow | cost=€0.000002 | sig=ed25519:xxxxx
            <br/>
            <br/>
            <strong>Step 8: Result</strong>
            <br/>
            ✓ Elena's booking: APPROVED for €450
            <br/>
            ✓ Proof: Immutable cryptographic receipt
            <br/>
            ✓ Compliance: 100% EU AI Act compliant
            <br/>
            <br/>
            <strong>If an auditor asks in 2 years:</strong>
            <br/>
            📋 Auditor: "Did you illegally process Elena's credit card?"
            <br/>
            🧑 You: "No, see this proof?" [Show receipt]
            <br/>
            ✓ Receipt shows: "PII access blocked by gate, human reviewed, masked card used, decision signed"
            <br/>
            📋 Auditor: "OK, you're compliant. Approved."
          </>
        }
      />

      {/* ========== SECTION 7: WHY EVERYTHING TOGETHER ========== */}
      <Section
        id="together"
        icon="🎬"
        title="WHY It All Works Together"
        description={
          <>
            <strong>The assembly line analogy (Toyota):</strong>
            <br/>
            <br/>
            Station 1: ⚙️ Robot (the agent) — does the work
            <br/>
            Station 2: 🔍 Quality Inspector (the gates) — stops mistakes
            <br/>
            Station 3: 📝 Recorder (agentacct) — documents everything
            <br/>
            Station 4: 📊 Monitor (Prometheus) — watches the line
            <br/>
            Station 5: 👀 Supervisor (you) — makes decisions
            <br/>
            <br/>
            <strong>Without this system:</strong>
            <br/>
            ❌ Robot does work → 💥 Mistake happens → 😱 No proof → 🚫 Lawsuit
            <br/>
            <br/>
            <strong>With this system:</strong>
            <br/>
            ✓ Robot starts → 🔍 Inspector checks → 👤 Supervisor approves → 📝 Recorded → ✅ Audit-ready
            <br/>
            <br/>
            <strong>The numbers that matter:</strong>
            <br/>
            ⚡ <strong>Speed:</strong> 39.3 tok/s inference (Rapid-MLX local)
            <br/>
            💰 <strong>Cost:</strong> €0.000001 per gate check (sub-cent decisions)
            <br/>
            🔐 <strong>Security:</strong> 0 Kbps egress (zero cloud exposure)
            <br/>
            ⏱️ <strong>Gate latency:</strong> 0.087ms (catches problems instantly)
            <br/>
            📋 <strong>Compliance:</strong> 100% EU AI Act Article 14 ready
          </>
        }
      />
    </div>
  )
}
