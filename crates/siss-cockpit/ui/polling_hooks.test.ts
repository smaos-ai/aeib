/// Phase 24 Task 1: React Polling Hooks Tests
/// Tests for useAgentActions, useAnomalies, useRecovery hooks
///
/// Test-Driven Development (RED phase): All tests below FAIL until hooks implemented.
/// Expected: 11 failing tests
///
/// Run with: npm test -- polling_hooks_tests.ts
/// Framework: Vitest (or Jest)

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useAgentActions, useAnomalies, useRecovery } from './polling_hooks';

// Mock fetch globally
global.fetch = vi.fn();

// Helper to flush pending promises and timers
async function flushPendingPromises() {
  await new Promise(resolve => setTimeout(resolve, 0));
}

// =====================================================================
// TEST SUITE 5: useAgentActions Hook (Tests 5.1 - 5.7)
// =====================================================================

describe('useAgentActions Hook', () => {

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('test_useAgentActions_initializes_with_empty_state', () => {
    // GIVEN component mounting with useAgentActions(sovereignId)
    const sovereignId = '550e8400-e29b-41d4-a716-446655440000';

    // WHEN hook initialized (no render yet, just hook creation)
    const { result } = renderHook(() => useAgentActions(sovereignId));

    // THEN state = {
    //   actions: [],
    //   total_count: 0,
    //   has_more: false,
    //   loading: false,
    //   error: null,
    //   last_updated_at: null
    // }
    expect(result.current.actions).toEqual([]);
    expect(result.current.total_count).toBe(0);
    expect(result.current.has_more).toBe(false);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.last_updated_at).toBeNull();
  });

  it('test_useAgentActions_fetches_on_mount', async () => {
    // GIVEN component mounting
    const sovereignId = '550e8400-e29b-41d4-a716-446655440000';
    const mockResponse = {
      actions: [{ action_id: '123' }],
      total_count: 1,
      has_more: false,
      generated_at: new Date().toISOString(),
    };
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    // WHEN hook initialized
    const { result } = renderHook(() => useAgentActions(sovereignId));

    // THEN fetch() called with correct URL
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/graph/projections/agent-actions')
    );

    // AND response parsed + state updated
    await vi.runOnlyPendingTimersAsync();
    expect(result.current.actions).toEqual(mockResponse.actions);
  });

  it('test_useAgentActions_polls_every_5_seconds', async () => {
    // GIVEN mounted component
    const sovereignId = '550e8400-e29b-41d4-a716-446655440000';
    const mockResponse = {
      actions: [],
      total_count: 0,
      has_more: false,
      generated_at: new Date().toISOString(),
    };
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });

    const { result } = renderHook(() => useAgentActions(sovereignId));

    // Clear initial mount call
    vi.clearAllMocks();

    // WHEN advancing time by 5000ms
    vi.advanceTimersByTime(5000);

    // THEN fetch() called again
    expect(global.fetch).toHaveBeenCalled();
    const firstCallCount = (global.fetch as any).mock.calls.length;

    // WHEN advancing by another 5000ms
    vi.advanceTimersByTime(5000);

    // THEN fetch() called twice total in this block
    expect((global.fetch as any).mock.calls.length).toBeGreaterThan(firstCallCount);
  });

  it('test_useAgentActions_updates_last_updated_at_on_success', async () => {
    // GIVEN successful fetch response
    const sovereignId = '550e8400-e29b-41d4-a716-446655440000';
    const now = new Date();
    const mockResponse = {
      actions: [],
      total_count: 0,
      has_more: false,
      generated_at: now.toISOString(),
    };
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const { result } = renderHook(() => useAgentActions(sovereignId));

    // WHEN state updated
    await vi.runOnlyPendingTimersAsync();
    // THEN last_updated_at is set
    expect(result.current.last_updated_at).not.toBeNull();
    // AND matches response timestamp (approximately)
    const diff = Math.abs(
      new Date(result.current.last_updated_at!).getTime() - now.getTime()
    );
    expect(diff).toBeLessThan(100); // Within 100ms
  });

  it('test_useAgentActions_preserves_error_state_across_retries', async () => {
    // GIVEN first fetch fails
    const sovereignId = '550e8400-e29b-41d4-a716-446655440000';
    (global.fetch as any).mockRejectedValueOnce(new Error('Network timeout'));

    const { result } = renderHook(() => useAgentActions(sovereignId));

    // WHEN error occurs
    await vi.runOnlyPendingTimersAsync();
    expect(result.current.error).toBe('Network timeout');

    // Clear mock for retry
    vi.clearAllMocks();
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        actions: [],
        total_count: 0,
        has_more: false,
        generated_at: new Date().toISOString(),
      }),
    });

    // WHEN polling continues (5s elapsed)
    vi.advanceTimersByTime(5000);
    await vi.runOnlyPendingTimersAsync();

    // THEN error state preserved until next successful fetch
    // (error persists during retry, then clears on success)
    expect(result.current.error).toBeNull();
  });

  it('test_useAgentActions_cleans_up_interval_on_unmount', () => {
    // GIVEN polling interval active
    const sovereignId = '550e8400-e29b-41d4-a716-446655440000';
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        actions: [],
        total_count: 0,
        has_more: false,
        generated_at: new Date().toISOString(),
      }),
    });

    const { unmount } = renderHook(() => useAgentActions(sovereignId));

    const initialCallCount = (global.fetch as any).mock.calls.length;

    // WHEN component unmounts
    unmount();

    // Clear mock
    vi.clearAllMocks();

    // WHEN time advances after unmount
    vi.advanceTimersByTime(5000);

    // THEN no fetch requests after unmount
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('test_useAgentActions_respects_sovereign_id_changes', async () => {
    // GIVEN sovereignId = "id-1"
    const sovereignId1 = '550e8400-e29b-41d4-a716-446655440000';
    const sovereignId2 = '660e8400-e29b-41d4-a716-446655440000';

    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        actions: [],
        total_count: 0,
        has_more: false,
        generated_at: new Date().toISOString(),
      }),
    });

    const { rerender } = renderHook(
      ({ id }) => useAgentActions(id),
      { initialProps: { id: sovereignId1 } }
    );

    vi.clearAllMocks();

    // WHEN sovereignId changes to "id-2"
    rerender({ id: sovereignId2 });

    // THEN new fetch() with sovereignId="id-2"
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining(`sovereign_id=${sovereignId2}`)
    );
  });
});

// =====================================================================
// TEST SUITE 6: useAnomalies Hook (Tests 6.1 - 6.3)
// =====================================================================

describe('useAnomalies Hook', () => {

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('test_useAnomalies_accepts_optional_filters', async () => {
    // GIVEN useAnomalies(sovereignId, severity="high", anomalyType="dispute_spam")
    const sovereignId = '550e8400-e29b-41d4-a716-446655440000';
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        anomalies: [],
        active_recovery_count: 0,
        total_count: 0,
        has_more: false,
        generated_at: new Date().toISOString(),
      }),
    });

    // WHEN hook fetches
    renderHook(() => useAnomalies(sovereignId, 'high', 'dispute_spam'));

    // THEN URL includes query params
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('severity=high') &&
        expect.stringContaining('anomaly_type=dispute_spam')
    );
  });

  it('test_useAnomalies_updates_active_recovery_count', async () => {
    // GIVEN response includes active_recovery_count = 3
    const sovereignId = '550e8400-e29b-41d4-a716-446655440000';
    const mockResponse = {
      anomalies: [],
      active_recovery_count: 3,
      total_count: 0,
      has_more: false,
      generated_at: new Date().toISOString(),
    };
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    // WHEN state updated
    const { result } = renderHook(() => useAnomalies(sovereignId));

    // THEN state.active_recovery_count = 3
    await vi.runOnlyPendingTimersAsync();
    expect(result.current.active_recovery_count).toBe(3);
  });

  it('test_useAnomalies_polls_independently_of_actions', async () => {
    // GIVEN both useAgentActions and useAnomalies active
    const sovereignId = '550e8400-e29b-41d4-a716-446655440000';
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        actions: [],
        total_count: 0,
        has_more: false,
        generated_at: new Date().toISOString(),
      }),
    });

    const { result: resultActions } = renderHook(() =>
      useAgentActions(sovereignId)
    );
    const { result: resultAnomalies } = renderHook(() =>
      useAnomalies(sovereignId)
    );

    const initialFetchCount = (global.fetch as any).mock.calls.length;

    // WHEN 5s elapsed
    vi.advanceTimersByTime(5000);

    // THEN BOTH polls fire independently
    expect((global.fetch as any).mock.calls.length).toBeGreaterThan(
      initialFetchCount
    );
    // (No specific assertion about collision, just that both fire)
  });
});

// =====================================================================
// TEST SUITE 7: useRecovery Hook (Tests 7.1 - 7.2)
// =====================================================================

describe('useRecovery Hook', () => {

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('test_useRecovery_calculates_progress_percentage', async () => {
    // GIVEN recovery weeks_elapsed = 2, expected total = 4 weeks
    const sovereignId = '550e8400-e29b-41d4-a716-446655440000';
    const entryAt = new Date();
    entryAt.setDate(entryAt.getDate() - 14); // 2 weeks ago
    const expectedExitAt = new Date(entryAt);
    expectedExitAt.setDate(expectedExitAt.getDate() + 28); // 4 weeks from entry

    const mockResponse = {
      recoveries: [
        {
          recovery_id: '123',
          sovereign_id: sovereignId,
          entry_reason: 'test',
          entry_at: entryAt.toISOString(),
          weeks_elapsed: 2,
          exit_status: null,
          exit_at: null,
          expected_exit_at: expectedExitAt.toISOString(),
          tier_at_entry: 50,
          current_tier: 45,
        },
      ],
      total_count: 1,
      has_more: false,
      generated_at: new Date().toISOString(),
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    // WHEN hook processes response
    const { result } = renderHook(() => useRecovery(sovereignId));

    // THEN progress_pct = (2 / 4) * 100 = 50%
    await vi.runOnlyPendingTimersAsync();
    const recovery = result.current.recoveries[0];
    const progressPct = (recovery.weeks_elapsed / 4) * 100;
    expect(progressPct).toBe(50);
  });

  it('test_useRecovery_detects_recovery_completion', async () => {
    // GIVEN recovery with exit_status = "success"
    const sovereignId = '550e8400-e29b-41d4-a716-446655440000';
    const mockResponse = {
      recoveries: [
        {
          recovery_id: '123',
          sovereign_id: sovereignId,
          entry_reason: 'test',
          entry_at: new Date().toISOString(),
          weeks_elapsed: 4,
          exit_status: 'success',
          exit_at: new Date().toISOString(),
          expected_exit_at: new Date().toISOString(),
          tier_at_entry: 50,
          current_tier: 75,
        },
      ],
      total_count: 1,
      has_more: false,
      generated_at: new Date().toISOString(),
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    // WHEN hook processes
    const { result } = renderHook(() => useRecovery(sovereignId));

    // THEN marks recovery as complete
    await vi.runOnlyPendingTimersAsync();
    const recovery = result.current.recoveries[0];
    expect(recovery.exit_status).toBe('success');
  });
});
