/**
 * Demo Banner Component
 * Displays when running in DEMO mode (public-safe)
 */

export default function DemoBanner() {
  return (
    <div style={{
      position: 'fixed',
      top: '60px',
      left: '0',
      right: '0',
      height: '32px',
      background: 'linear-gradient(90deg, #f59e0b 0%, #f97316 100%)',
      color: '#000',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: '11px',
      fontWeight: 'bold',
      letterSpacing: '1px',
      zIndex: 997,
      borderBottom: '2px solid #ea580c'
    }}>
      🎬 DEMO MODE — This is a public demonstration. No real AI running. Real system uses actual backend + ML models.
    </div>
  )
}
