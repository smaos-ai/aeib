import { useState, useEffect } from 'react'

export default function NavigationControls({ currentStep, totalSteps, onNext, onPrev, onPause, isPaused, animationSpeed }) {
  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%)',
      border: '2px solid #3b82f6',
      borderRadius: '12px',
      padding: '14px',
      marginBottom: '16px',
      backdropFilter: 'blur(8px)'
    }}>
      {/* Header */}
      <div style={{
        fontSize: '11px',
        fontWeight: 'bold',
        color: '#3b82f6',
        marginBottom: '12px',
        textTransform: 'uppercase',
        letterSpacing: '1px'
      }}>
        ⏯️ Navigation & Analysis Controls
      </div>

      {/* Progress Bar */}
      <div style={{
        background: 'rgba(26, 31, 58, 0.6)',
        border: '1px solid rgba(59, 130, 246, 0.3)',
        borderRadius: '8px',
        padding: '8px',
        marginBottom: '12px',
        overflow: 'hidden'
      }}>
        <div style={{
          fontSize: '10px',
          color: '#a0a0a0',
          marginBottom: '6px',
          display: 'flex',
          justifyContent: 'space-between'
        }}>
          <span>Progress</span>
          <span>{currentStep} / {totalSteps}</span>
        </div>
        <div style={{
          width: '100%',
          height: '6px',
          background: 'rgba(0, 0, 0, 0.3)',
          borderRadius: '3px',
          overflow: 'hidden'
        }}>
          <div style={{
            width: `${(currentStep / totalSteps) * 100}%`,
            height: '100%',
            background: 'linear-gradient(90deg, #3b82f6 0%, #10b981 100%)',
            transition: 'width 0.3s ease'
          }}/>
        </div>
      </div>

      {/* Controls */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr 1fr',
        gap: '8px',
        marginBottom: '12px'
      }}>
        {/* Previous Button */}
        <button
          onClick={onPrev}
          disabled={currentStep <= 1}
          style={{
            padding: '8px',
            background: currentStep <= 1 ? 'rgba(100, 116, 139, 0.2)' : 'linear-gradient(135deg, rgba(239, 68, 68, 0.2) 0%, rgba(239, 68, 68, 0.1) 100%)',
            border: currentStep <= 1 ? '1px solid rgba(100, 116, 139, 0.3)' : '2px solid #ef4444',
            borderRadius: '8px',
            color: currentStep <= 1 ? '#4b5563' : '#ef4444',
            fontSize: '11px',
            fontWeight: 'bold',
            cursor: currentStep <= 1 ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s ease',
            opacity: currentStep <= 1 ? 0.5 : 1
          }}
        >
          ◀ Previous
        </button>

        {/* Pause/Resume Button */}
        <button
          onClick={onPause}
          style={{
            padding: '8px',
            background: isPaused
              ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(16, 185, 129, 0.1) 100%)'
              : 'linear-gradient(135deg, rgba(245, 158, 11, 0.2) 0%, rgba(245, 158, 11, 0.1) 100%)',
            border: isPaused ? '2px solid #10b981' : '2px solid #f59e0b',
            borderRadius: '8px',
            color: isPaused ? '#10b981' : '#f59e0b',
            fontSize: '11px',
            fontWeight: 'bold',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
        >
          {isPaused ? '▶ Resume' : '⏸ Pause'}
        </button>

        {/* Next Button */}
        <button
          onClick={onNext}
          disabled={currentStep >= totalSteps}
          style={{
            padding: '8px',
            background: currentStep >= totalSteps ? 'rgba(100, 116, 139, 0.2)' : 'linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(16, 185, 129, 0.1) 100%)',
            border: currentStep >= totalSteps ? '1px solid rgba(100, 116, 139, 0.3)' : '2px solid #10b981',
            borderRadius: '8px',
            color: currentStep >= totalSteps ? '#4b5563' : '#10b981',
            fontSize: '11px',
            fontWeight: 'bold',
            cursor: currentStep >= totalSteps ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s ease',
            opacity: currentStep >= totalSteps ? 0.5 : 1
          }}
        >
          Next ▶
        </button>
      </div>

      {/* Animation Speed Control */}
      <div style={{
        fontSize: '10px',
        color: '#a0a0a0',
        marginBottom: '6px'
      }}>
        Animation Speed: <span style={{ color: '#3b82f6', fontWeight: 'bold' }}>{animationSpeed}x</span>
      </div>
      <div style={{
        display: 'flex',
        gap: '4px'
      }}>
        {['0.5x', '1x', '2x'].map(speed => (
          <button
            key={speed}
            style={{
              flex: 1,
              padding: '6px',
              background: animationSpeed === parseFloat(speed)
                ? 'rgba(59, 130, 246, 0.3)'
                : 'rgba(26, 31, 58, 0.6)',
              border: `1px solid ${animationSpeed === parseFloat(speed) ? '#3b82f6' : 'rgba(100, 116, 139, 0.3)'}`,
              borderRadius: '6px',
              color: animationSpeed === parseFloat(speed) ? '#3b82f6' : '#a0a0a0',
              fontSize: '10px',
              fontWeight: 'bold',
              cursor: 'pointer',
              transition: 'all 0.2s ease'
            }}
          >
            {speed}
          </button>
        ))}
      </div>

      {/* Info Text */}
      <div style={{
        fontSize: '9px',
        color: '#4b5563',
        marginTop: '12px',
        paddingTop: '8px',
        borderTop: '1px solid rgba(45, 55, 72, 0.3)',
        lineHeight: '1.4'
      }}>
        💡 <strong>Tip:</strong> Use Previous/Next to go at your own pace. Click Pause to analyze each step. Adjust animation speed for slower observation.
      </div>
    </div>
  )
}
