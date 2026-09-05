import { useState, useEffect } from 'react'

export default function SystemStatus() {
  const [statusResults, setStatusResults] = useState({})
  const [isChecking, setIsChecking] = useState(false)
  const [autoMonitor, setAutoMonitor] = useState(false)
  const [systemHealth, setSystemHealth] = useState('healthy')
  const [lastCheck, setLastCheck] = useState(null)

  const services = [
    {
      name: 'Frontend (Vite)',
      port: 5173,
      url: 'http://localhost:5173',
      description: 'React app (you are here now)',
      endpoint: '/',
      checkable: true,
      critical: false,
      startCmd: 'cd /Users/andriileukhin/Documents/SovereignNexus/frontend && npm run dev',
      stopCmd: 'lsof -ti:5173 | xargs kill -9',
      container: null
    },
    {
      name: 'Sandbox Pool Manager',
      port: 8080,
      url: 'http://localhost:8080',
      description: 'FastAPI sandbox orchestration',
      endpoint: '/api/pool/status',
      checkable: true,
      critical: true,
      startCmd: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml up -d sandbox-pool',
      stopCmd: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml stop sandbox-pool',
      container: 'sandbox-pool'
    },
    {
      name: 'Prometheus (Metrics)',
      port: 9090,
      url: 'http://localhost:9090',
      description: 'Time-series database for monitoring',
      endpoint: '/graph',
      checkable: true,
      critical: false,
      startCmd: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml up -d prometheus',
      stopCmd: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml stop prometheus',
      container: 'prometheus'
    },
    {
      name: 'Grafana (Dashboards)',
      port: 3001,
      url: 'http://localhost:3001',
      description: 'Visualization of Prometheus metrics',
      endpoint: '/',
      checkable: true,
      critical: false,
      startCmd: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml up -d grafana',
      stopCmd: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml stop grafana',
      container: 'grafana'
    },
    {
      name: 'Log Streamer (SSE)',
      port: 8081,
      url: 'http://localhost:8081',
      description: 'Server-Sent Events for live logs',
      endpoint: '/stream',
      checkable: true,
      critical: false,
      startCmd: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml up -d log-streamer',
      stopCmd: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml stop log-streamer',
      container: 'log-streamer'
    },
    {
      name: 'PostgreSQL (Database)',
      port: 5432,
      url: 'localhost:5432',
      description: 'Guest records & compliance data',
      endpoint: 'psql -h localhost -U smaos -d smaos_db',
      checkable: false,
      critical: true,
      startCmd: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml up -d postgres',
      stopCmd: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml stop postgres',
      container: 'postgres'
    },
    {
      name: 'Docker Desktop',
      port: null,
      url: 'Desktop app',
      description: 'Container orchestration (docker-compose)',
      endpoint: 'docker ps',
      checkable: false,
      critical: true,
      startCmd: 'open -a "Docker"',
      stopCmd: 'N/A - Use System Preferences',
      container: null
    }
  ]

  // Auto-monitor system health
  useEffect(() => {
    if (!autoMonitor) return

    const interval = setInterval(() => {
      let healthy = 0
      let offline = 0

      services.forEach(service => {
        if (service.checkable && statusResults[service.name]) {
          if (statusResults[service.name].status.includes('✅')) {
            healthy++
          } else {
            offline++
          }
        }
      })

      if (offline === 0 && healthy === services.filter(s => s.checkable).length) {
        setSystemHealth('healthy')
      } else if (offline > 0 && healthy > 0) {
        setSystemHealth('degraded')
      } else if (offline > 0) {
        setSystemHealth('critical')
      }

      setLastCheck(new Date().toLocaleTimeString())
    }, 2000)

    return () => clearInterval(interval)
  }, [autoMonitor, statusResults])

  const handleCheckService = async (service) => {
    setIsChecking(true)
    try {
      const res = await fetch(service.url + service.endpoint, {
        method: 'GET',
        mode: 'cors',
        headers: { 'Content-Type': 'application/json' }
      })
      setStatusResults(prev => ({
        ...prev,
        [service.name]: {
          status: res.ok ? '✅ RUNNING' : '❌ NOT RESPONDING',
          code: res.status
        }
      }))
    } catch (e) {
      setStatusResults(prev => ({
        ...prev,
        [service.name]: {
          status: '❌ OFFLINE',
          error: e.message
        }
      }))
    }
    setIsChecking(false)
  }

  const handleCopyUrl = (url) => {
    navigator.clipboard.writeText(url)
    alert(`Copied: ${url}`)
  }

  return (
    <div style={{ padding: '0' }}>
      <div style={{
        fontSize: '11px',
        fontWeight: 'bold',
        color: '#3b82f6',
        marginBottom: '14px',
        textTransform: 'uppercase',
        letterSpacing: '1px'
      }}>
        🔍 System Running Status & Port Map
      </div>

      <div style={{
        background: 'rgba(16, 185, 129, 0.1)',
        border: '1px solid rgba(16, 185, 129, 0.3)',
        borderRadius: '8px',
        padding: '12px',
        marginBottom: '16px',
        fontSize: '10px',
        color: '#a0a0a0'
      }}>
        ✅ <strong>What's running:</strong> Click "Check Status" to verify each service is online.
        Copy any URL to browser. Use command lines to debug from terminal.
      </div>

      {/* Quick Links */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%)',
        border: '2px solid #3b82f6',
        borderRadius: '12px',
        padding: '14px',
        marginBottom: '16px',
        backdropFilter: 'blur(8px)'
      }}>
        <div style={{
          fontSize: '10px',
          fontWeight: 'bold',
          color: '#3b82f6',
          marginBottom: '10px',
          textTransform: 'uppercase'
        }}>
          🔗 Quick Links (Copy & Paste)
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '8px'
        }}>
          {services.filter(s => s.url.startsWith('http')).map(service => (
            <button
              key={service.name}
              onClick={() => handleCopyUrl(service.url + service.endpoint)}
              style={{
                padding: '8px',
                background: 'rgba(26, 31, 58, 0.6)',
                border: '1px solid rgba(59, 130, 246, 0.3)',
                borderRadius: '6px',
                color: '#3b82f6',
                fontSize: '9px',
                fontWeight: 'bold',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                textAlign: 'left',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(59, 130, 246, 0.2)'
                e.currentTarget.style.borderColor = '#3b82f6'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(26, 31, 58, 0.6)'
                e.currentTarget.style.borderColor = 'rgba(59, 130, 246, 0.3)'
              }}
              title={`Click to copy: ${service.url}${service.endpoint}`}
            >
              📋 {service.name}
            </button>
          ))}
        </div>
      </div>

      {/* Auto-Monitor Toggle */}
      <div style={{
        background: systemHealth === 'healthy'
          ? 'rgba(16, 185, 129, 0.1)'
          : systemHealth === 'degraded'
          ? 'rgba(245, 158, 11, 0.1)'
          : 'rgba(239, 68, 68, 0.1)',
        border: `2px solid ${systemHealth === 'healthy' ? '#10b981' : systemHealth === 'degraded' ? '#f59e0b' : '#ef4444'}`,
        borderRadius: '12px',
        padding: '12px',
        marginBottom: '16px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        backdropFilter: 'blur(8px)'
      }}>
        <div>
          <div style={{
            fontSize: '11px',
            fontWeight: 'bold',
            color: systemHealth === 'healthy' ? '#10b981' : systemHealth === 'degraded' ? '#f59e0b' : '#ef4444'
          }}>
            {systemHealth === 'healthy' && '✅ SYSTEM HEALTHY'}
            {systemHealth === 'degraded' && '⚠️ SYSTEM DEGRADED'}
            {systemHealth === 'critical' && '❌ SYSTEM CRITICAL'}
          </div>
          <div style={{
            fontSize: '9px',
            color: '#a0a0a0',
            marginTop: '4px'
          }}>
            Last check: {lastCheck || 'Never'}
          </div>
        </div>

        <button
          onClick={() => {
            setAutoMonitor(!autoMonitor)
            if (!autoMonitor) {
              // Start checking all services immediately
              services.forEach(service => {
                if (service.checkable) handleCheckService(service)
              })
            }
          }}
          style={{
            padding: '8px 14px',
            background: autoMonitor
              ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.3) 0%, rgba(16, 185, 129, 0.1) 100%)'
              : 'linear-gradient(135deg, rgba(59, 130, 246, 0.3) 0%, rgba(59, 130, 246, 0.1) 100%)',
            border: `2px solid ${autoMonitor ? '#10b981' : '#3b82f6'}`,
            borderRadius: '8px',
            color: autoMonitor ? '#10b981' : '#3b82f6',
            fontSize: '10px',
            fontWeight: 'bold',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            whiteSpace: 'nowrap'
          }}
        >
          {autoMonitor ? '🔴 Stop Monitoring' : '🟢 Start Auto-Monitor'}
        </button>
      </div>

      {/* Service Details */}
      <div style={{
        fontSize: '10px',
        fontWeight: 'bold',
        color: '#3b82f6',
        marginBottom: '12px',
        textTransform: 'uppercase'
      }}>
        📍 Service Details & Control
      </div>

      {services.map((service, i) => {
        const isOnline = statusResults[service.name]?.status.includes('✅')

        return (
        <div
          key={i}
          style={{
            background: isOnline
              ? 'rgba(16, 185, 129, 0.05)'
              : statusResults[service.name]
              ? 'rgba(239, 68, 68, 0.05)'
              : 'rgba(26, 31, 58, 0.6)',
            border: isOnline
              ? '2px solid rgba(16, 185, 129, 0.4)'
              : statusResults[service.name]
              ? '2px solid rgba(239, 68, 68, 0.4)'
              : '1px solid rgba(100, 116, 139, 0.3)',
            borderRadius: '10px',
            padding: '12px',
            marginBottom: '10px',
            transition: 'all 0.3s ease'
          }}
        >
          {/* Service Name & Status */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '8px'
          }}>
            <div style={{
              display: 'flex',
              gap: '8px',
              alignItems: 'center'
            }}>
              <div style={{
                fontSize: '11px',
                fontWeight: 'bold',
                color: '#3b82f6'
              }}>
                {service.name}
              </div>
              <div style={{
                fontSize: '8px',
                fontWeight: 'bold',
                background: service.critical ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                border: `1px solid ${service.critical ? '#ef4444' : '#f59e0b'}`,
                color: service.critical ? '#ef4444' : '#f59e0b',
                padding: '2px 6px',
                borderRadius: '3px'
              }}>
                {service.critical ? '🔴 CRITICAL' : '🟡 OPTIONAL'}
              </div>
            </div>
            {statusResults[service.name] && (
              <div style={{
                fontSize: '10px',
                fontWeight: 'bold',
                color: statusResults[service.name].status.includes('✅') ? '#10b981' : '#ef4444',
                animation: statusResults[service.name].status.includes('❌') ? 'pulse 1s infinite' : 'none'
              }}>
                {statusResults[service.name].status}
              </div>
            )}
          </div>

          {/* Description */}
          <div style={{
            fontSize: '9px',
            color: '#a0a0a0',
            marginBottom: '8px'
          }}>
            {service.description}
          </div>

          {/* Port & URL */}
          <div style={{
            background: 'rgba(0, 0, 0, 0.3)',
            border: '1px solid rgba(100, 116, 139, 0.2)',
            borderRadius: '6px',
            padding: '8px',
            marginBottom: '8px',
            fontFamily: 'monospace',
            fontSize: '9px',
            color: '#a0a0a0',
            overflowX: 'auto'
          }}>
            {service.port ? (
              <>
                <div>🔌 Port: <strong style={{ color: '#10b981' }}>{service.port}</strong></div>
                <div>🌐 URL: <strong style={{ color: '#3b82f6' }}>{service.url}{service.endpoint}</strong></div>
              </>
            ) : (
              <>
                <div>📍 {service.url}</div>
                <div>⚙️ Command: <strong style={{ color: '#3b82f6' }}>{service.endpoint}</strong></div>
              </>
            )}
          </div>

          {/* Action Buttons */}
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '6px'
          }}>
            {service.checkable && (
              <button
                onClick={() => handleCheckService(service)}
                disabled={isChecking}
                style={{
                  padding: '6px 10px',
                  background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(16, 185, 129, 0.1) 100%)',
                  border: '1px solid #10b981',
                  borderRadius: '6px',
                  color: '#10b981',
                  fontSize: '9px',
                  fontWeight: 'bold',
                  cursor: isChecking ? 'not-allowed' : 'pointer',
                  transition: 'all 0.2s ease',
                  opacity: isChecking ? 0.5 : 1
                }}
              >
                {isChecking ? '⟳ Checking...' : '✓ Check Status'}
              </button>
            )}

            {/* START Command */}
            <button
              onClick={() => {
                navigator.clipboard.writeText(service.startCmd)
                alert(`📋 Copied START command:\n\n${service.startCmd}\n\nPaste in terminal to start ${service.name}`)
              }}
              style={{
                padding: '6px 10px',
                background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.25) 0%, rgba(16, 185, 129, 0.1) 100%)',
                border: '2px solid #10b981',
                borderRadius: '6px',
                color: '#10b981',
                fontSize: '9px',
                fontWeight: 'bold',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'linear-gradient(135deg, rgba(16, 185, 129, 0.4) 0%, rgba(16, 185, 129, 0.2) 100%)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'linear-gradient(135deg, rgba(16, 185, 129, 0.25) 0%, rgba(16, 185, 129, 0.1) 100%)'
              }}
              title={`START: ${service.startCmd}`}
            >
              ▶ START
            </button>

            {/* STOP Command */}
            <button
              onClick={() => {
                navigator.clipboard.writeText(service.stopCmd)
                alert(`📋 Copied STOP command:\n\n${service.stopCmd}\n\nPaste in terminal to stop ${service.name}`)
              }}
              style={{
                padding: '6px 10px',
                background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.25) 0%, rgba(239, 68, 68, 0.1) 100%)',
                border: '2px solid #ef4444',
                borderRadius: '6px',
                color: '#ef4444',
                fontSize: '9px',
                fontWeight: 'bold',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'linear-gradient(135deg, rgba(239, 68, 68, 0.4) 0%, rgba(239, 68, 68, 0.2) 100%)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'linear-gradient(135deg, rgba(239, 68, 68, 0.25) 0%, rgba(239, 68, 68, 0.1) 100%)'
              }}
              title={`STOP: ${service.stopCmd}`}
            >
              ⏹ STOP
            </button>

            {service.url.startsWith('http') && (
              <>
                <button
                  onClick={() => handleCopyUrl(service.url + service.endpoint)}
                  style={{
                    padding: '6px 10px',
                    background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.2) 0%, rgba(59, 130, 246, 0.1) 100%)',
                    border: '1px solid #3b82f6',
                    borderRadius: '6px',
                    color: '#3b82f6',
                    fontSize: '9px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                >
                  📋 Copy URL
                </button>
                <a
                  href={service.url + service.endpoint}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    padding: '6px 10px',
                    background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.2) 0%, rgba(245, 158, 11, 0.1) 100%)',
                    border: '1px solid #f59e0b',
                    borderRadius: '6px',
                    color: '#f59e0b',
                    fontSize: '9px',
                    fontWeight: 'bold',
                    textDecoration: 'none',
                    transition: 'all 0.2s ease',
                    display: 'inline-block'
                  }}
                >
                  🔗 Open
                </a>
              </>
            )}
          </div>
        </div>
        )
      })}

      {/* Terminal Commands */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(245, 158, 11, 0.05) 100%)',
        border: '2px solid #f59e0b',
        borderRadius: '12px',
        padding: '14px',
        marginTop: '16px',
        backdropFilter: 'blur(8px)'
      }}>
        <div style={{
          fontSize: '10px',
          fontWeight: 'bold',
          color: '#f59e0b',
          marginBottom: '10px',
          textTransform: 'uppercase'
        }}>
          💻 Terminal Commands (Copy & Paste)
        </div>

        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '8px'
        }}>
          {[
            { cmd: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml up -d', desc: 'Start all containers' },
            { cmd: 'docker-compose -f ~/.smaos/sandbox/docker-compose.yml ps', desc: 'View running containers' },
            { cmd: 'docker logs sandbox-pool -f', desc: 'Watch sandbox pool logs' },
            { cmd: 'curl http://localhost:8080/api/pool/status', desc: 'Check sandbox pool status' },
            { cmd: 'psql -h localhost -U smaos -d smaos_db -c "SELECT COUNT(*) FROM guests;"', desc: 'Query PostgreSQL' }
          ].map((item, i) => (
            <div
              key={i}
              style={{
                background: 'rgba(0, 0, 0, 0.3)',
                border: '1px solid rgba(245, 158, 11, 0.2)',
                borderRadius: '6px',
                padding: '8px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <div>
                <div style={{
                  fontSize: '9px',
                  color: '#a0a0a0',
                  marginBottom: '4px'
                }}>
                  {item.desc}
                </div>
                <div style={{
                  fontFamily: 'monospace',
                  fontSize: '8px',
                  color: '#f59e0b',
                  wordBreak: 'break-all'
                }}>
                  {item.cmd}
                </div>
              </div>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(item.cmd)
                  alert(`Copied command`)
                }}
                style={{
                  padding: '4px 8px',
                  background: 'rgba(245, 158, 11, 0.2)',
                  border: '1px solid #f59e0b',
                  borderRadius: '4px',
                  color: '#f59e0b',
                  fontSize: '8px',
                  fontWeight: 'bold',
                  cursor: 'pointer',
                  flexShrink: 0,
                  whiteSpace: 'nowrap'
                }}
              >
                📋 Copy
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* System Requirements */}
      <div style={{
        background: 'rgba(99, 102, 241, 0.1)',
        border: '1px solid rgba(99, 102, 241, 0.3)',
        borderRadius: '8px',
        padding: '12px',
        marginTop: '16px',
        fontSize: '10px',
        color: '#a0a0a0',
        lineHeight: '1.5'
      }}>
        <strong style={{ color: '#6366f1' }}>📋 What You Need to Run SMAOS:</strong>
        <div style={{ marginTop: '8px' }}>
          ✅ Docker Desktop (running) → All containers<br/>
          ✅ Node.js 18+ → Frontend dev server<br/>
          ✅ Python 3.12+ → Sandbox pool API<br/>
          ✅ PostgreSQL 14+ → Database<br/>
          ✅ 8GB+ RAM → Containers + services<br/>
          ✅ Ports 5173, 8080, 9090, 3001, 8081, 5432 → Free & available
        </div>
      </div>

      {/* Graceful Degradation Guide */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(168, 85, 247, 0.1) 0%, rgba(168, 85, 247, 0.05) 100%)',
        border: '2px solid #a855f7',
        borderRadius: '12px',
        padding: '14px',
        marginTop: '16px',
        backdropFilter: 'blur(8px)'
      }}>
        <div style={{
          fontSize: '11px',
          fontWeight: 'bold',
          color: '#a855f7',
          marginBottom: '10px',
          textTransform: 'uppercase'
        }}>
          🔄 Test Graceful Degradation
        </div>

        <div style={{
          fontSize: '9px',
          color: '#a0a0a0',
          lineHeight: '1.6'
        }}>
          <strong>How to test:</strong>
          <div style={{ marginTop: '8px', marginBottom: '8px' }}>
            1. Click ▶ START to open new terminal window<br/>
            2. System auto-monitors & detects online/offline<br/>
            3. Click ⏹ STOP to disable a service<br/>
            4. Watch UI show: <span style={{ color: '#f59e0b' }}>⚠️ DEGRADED</span> or <span style={{ color: '#ef4444' }}>❌ CRITICAL</span>
          </div>

          <strong style={{ color: '#a855f7' }}>Expected Behavior:</strong>
          <div style={{ marginTop: '8px' }}>
            <strong style={{ color: '#10b981' }}>Optional services down</strong> (Prometheus, Grafana, Logs): System still works ✅<br/>
            <strong style={{ color: '#ef4444' }}>Critical services down</strong> (Sandbox Pool, DB): System fails gracefully ⚠️
          </div>
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
      `}</style>
    </div>
  )
}
