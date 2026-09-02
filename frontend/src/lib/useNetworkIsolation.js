import { useState, useEffect } from 'react'

/**
 * Hook to continuously poll network isolation status.
 * Returns { isolated, browserOnline, testsPassed, lastCheck, loading, error }
 *
 * VERDICT LOGIC (fixes the bug from NetworkIsolationTerminal.jsx):
 * - navigator.onLine is PRIMARY (most reliable)
 * - Fetch to 8.8.8.8 is SECONDARY (unreliable: no TLS cert for bare IP, CORS blocked)
 * - If navigator.onLine says CONNECTED but fetch fails, result is INCONCLUSIVE (not "isolated")
 * - Only show "VERIFIED ISOLATED" if navigator.onLine === false AND fetch fails
 */

export function useNetworkIsolation(pollIntervalMs = 7000) {
  const [status, setStatus] = useState({
    isolated: false,
    browserOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
    testsPassed: [],
    testsFailed: [],
    lastCheck: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    // Initial test on mount
    runNetworkTest()

    // Poll every N seconds
    const interval = setInterval(runNetworkTest, pollIntervalMs)

    // Also listen to online/offline events for immediate feedback
    const handleOnline = () => setStatus(s => ({ ...s, browserOnline: true }))
    const handleOffline = () => setStatus(s => ({ ...s, browserOnline: false }))

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      clearInterval(interval)
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [pollIntervalMs])

  async function runNetworkTest() {
    setStatus(s => ({ ...s, loading: true, error: null }))

    const testsPassed = []
    const testsFailed = []

    // Test 1: Browser network state (PRIMARY signal)
    const browserOnline = navigator.onLine
    if (browserOnline) {
      testsFailed.push('Browser reports: CONNECTED')
    } else {
      testsPassed.push('Browser reports: OFFLINE')
    }

    // Test 2: Attempt to reach external IP (unreliable, but informative)
    let fetchSucceeded = false
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 2000)
      const response = await fetch('https://8.8.8.8', {
        signal: controller.signal,
        method: 'HEAD',
      })
      clearTimeout(timeoutId)
      fetchSucceeded = true
      testsFailed.push('External IP reachable (8.8.8.8 responded)')
    } catch (err) {
      // Expected: bare IP has no valid TLS cert, CORS blocked, or network error
      testsPassed.push('External IP unreachable (8.8.8.8 timeout/blocked)')
    }

    // VERDICT: reconcile the two signals
    // navigator.onLine is authoritative; fetch can be misleading
    let isolated = false
    let verdict = 'INCONCLUSIVE'

    if (!browserOnline && !fetchSucceeded) {
      isolated = true
      verdict = 'VERIFIED ISOLATED'
    } else if (browserOnline && !fetchSucceeded) {
      isolated = false
      verdict = 'INCONCLUSIVE (browser online, fetch blocked)'
    } else if (browserOnline && fetchSucceeded) {
      isolated = false
      verdict = 'CONNECTED (browser + fetch confirmed)'
    } else {
      // browserOnline=false but fetch succeeded (unlikely but possible in testing)
      isolated = false
      verdict = 'INCONCLUSIVE (browser offline, fetch succeeded)'
    }

    setStatus({
      isolated,
      browserOnline,
      testsPassed,
      testsFailed,
      verdict,
      lastCheck: new Date(),
      loading: false,
      error: null,
    })
  }

  return status
}
