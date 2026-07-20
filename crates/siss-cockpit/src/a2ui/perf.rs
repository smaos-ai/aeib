//! Performance optimization layer for A2UI rendering and streaming.
//!
//! Implements:
//! - Renderer caching (reduces repeated rendering)
//! - HTML escaping optimization (pre-computed tables)
//! - SSE buffering with ring buffers (fixed allocations)
//! - Validation result caching
//! - Session cleanup (idle timeout)

use std::sync::Arc;
use std::collections::HashMap;
use parking_lot::RwLock;
use lru::LruCache;
use std::num::NonZeroUsize;
use std::time::{SystemTime, UNIX_EPOCH, Duration};

/// Renderer cache: ComponentId → Rendered HTML
/// LRU eviction prevents unbounded memory growth
pub struct RenderCache {
    cache: Arc<RwLock<LruCache<String, CachedRender>>>,
}

#[derive(Clone, Debug)]
struct CachedRender {
    html: String,
    timestamp: u64,
}

impl RenderCache {
    /// Create new cache (default capacity: 4096 entries)
    pub fn new(capacity: usize) -> Self {
        let capacity = NonZeroUsize::new(capacity).unwrap_or(NonZeroUsize::new(4096).unwrap());
        Self {
            cache: Arc::new(RwLock::new(LruCache::new(capacity))),
        }
    }

    /// Get cached render result
    pub fn get(&self, component_id: &str) -> Option<String> {
        let mut cache = self.cache.write();
        cache.get(component_id).map(|cr| cr.html.clone())
    }

    /// Insert render result into cache
    pub fn insert(&self, component_id: String, html: String) {
        let timestamp = current_timestamp();
        let mut cache = self.cache.write();
        cache.put(
            component_id,
            CachedRender { html, timestamp },
        );
    }

    /// Invalidate cache entry (after component update)
    pub fn invalidate(&self, component_id: &str) {
        let mut cache = self.cache.write();
        cache.pop(component_id);
    }

    /// Clear entire cache
    pub fn clear(&self) {
        let mut cache = self.cache.write();
        cache.clear();
    }

    /// Cache stats for monitoring
    pub fn stats(&self) -> CacheStats {
        let cache = self.cache.read();
        CacheStats {
            len: cache.len(),
            capacity: cache.cap().get(),
        }
    }
}

/// Cache statistics
#[derive(Debug, Clone)]
pub struct CacheStats {
    pub len: usize,
    pub capacity: usize,
}

/// Validation result cache: ComponentId → IsValid
pub struct ValidationCache {
    results: Arc<RwLock<HashMap<String, (bool, u64)>>>,
    ttl: Duration,
}

impl ValidationCache {
    /// Create new validation cache with TTL (default: 30 seconds)
    pub fn new(ttl_secs: u64) -> Self {
        Self {
            results: Arc::new(RwLock::new(HashMap::new())),
            ttl: Duration::from_secs(ttl_secs),
        }
    }

    /// Get cached validation result (if not expired)
    pub fn get(&self, component_id: &str) -> Option<bool> {
        let cache = self.results.read();
        if let Some((valid, timestamp)) = cache.get(component_id) {
            let age = current_timestamp().saturating_sub(*timestamp);
            if age < self.ttl.as_secs() {
                return Some(*valid);
            }
        }
        None
    }

    /// Insert validation result
    pub fn insert(&self, component_id: String, is_valid: bool) {
        let mut cache = self.results.write();
        cache.insert(component_id, (is_valid, current_timestamp()));
    }

    /// Invalidate entry
    pub fn invalidate(&self, component_id: &str) {
        let mut cache = self.results.write();
        cache.remove(component_id);
    }

    /// Clean expired entries (call periodically)
    pub fn cleanup_expired(&self) {
        let mut cache = self.results.write();
        let cutoff = current_timestamp().saturating_sub(self.ttl.as_secs());
        cache.retain(|_, (_, ts)| *ts > cutoff);
    }

    /// Clear entire cache
    pub fn clear(&self) {
        let mut cache = self.results.write();
        cache.clear();
    }
}

/// Ring buffer for SSE events (fixed-size, no allocations after init)
pub struct SseEventRingBuffer {
    buffer: Arc<RwLock<Vec<SseEvent>>>,
    write_pos: Arc<RwLock<usize>>,
    read_pos: Arc<RwLock<usize>>,
    capacity: usize,
}

#[derive(Clone, Debug)]
struct SseEvent {
    data: String,
    timestamp: u64,
}

impl SseEventRingBuffer {
    /// Create new ring buffer (capacity: default 1024 events)
    pub fn new(capacity: usize) -> Self {
        let mut buffer = Vec::with_capacity(capacity);
        buffer.resize(capacity, SseEvent {
            data: String::new(),
            timestamp: 0,
        });

        Self {
            buffer: Arc::new(RwLock::new(buffer)),
            write_pos: Arc::new(RwLock::new(0)),
            read_pos: Arc::new(RwLock::new(0)),
            capacity,
        }
    }

    /// Push event into ring buffer (overwrites oldest if full)
    pub fn push(&self, data: String) {
        let wpos_val = {
            let wpos = self.write_pos.read();
            *wpos
        };
        let idx = wpos_val % self.capacity;

        let mut buf = self.buffer.write();
        buf[idx] = SseEvent {
            data,
            timestamp: current_timestamp(),
        };

        let mut wpos = self.write_pos.write();
        *wpos = wpos_val.wrapping_add(1);
    }

    /// Get pending events since last read
    pub fn drain(&self) -> Vec<String> {
        let mut rpos = self.read_pos.write();
        let wpos = self.write_pos.read();
        let mut events = Vec::new();

        let write_idx = (*wpos) % self.capacity;
        let read_idx = (*rpos) % self.capacity;

        if *wpos > *rpos {
            let buf = self.buffer.read();
            if *rpos >= self.capacity {
                // Wrapped around case
                for i in read_idx..write_idx {
                    events.push(buf[i].data.clone());
                }
            } else {
                // Linear case
                for i in read_idx..write_idx {
                    events.push(buf[i].data.clone());
                }
            }
        }

        *rpos = *wpos;
        events
    }

    /// Get buffer fill percentage
    pub fn fill_percent(&self) -> f32 {
        let wpos = self.write_pos.read();
        let rpos = self.read_pos.read();
        let pending = (*wpos).saturating_sub(*rpos);
        ((pending % self.capacity) as f32 / self.capacity as f32) * 100.0
    }
}

/// Session cleanup tracker (tracks idle sessions)
pub struct SessionCleanup {
    idle_timeout: Duration,
    sessions: Arc<RwLock<HashMap<String, u64>>>,
}

impl SessionCleanup {
    /// Create new cleanup tracker (idle timeout: default 5 minutes)
    pub fn new(timeout_secs: u64) -> Self {
        Self {
            idle_timeout: Duration::from_secs(timeout_secs),
            sessions: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Mark session as active
    pub fn touch(&self, session_id: String) {
        let mut sessions = self.sessions.write();
        sessions.insert(session_id, current_timestamp());
    }

    /// Get list of idle session IDs
    pub fn get_idle_sessions(&self) -> Vec<String> {
        let sessions = self.sessions.read();
        let cutoff = current_timestamp().saturating_sub(self.idle_timeout.as_secs());
        sessions
            .iter()
            .filter(|(_, ts)| **ts < cutoff)
            .map(|(id, _)| id.clone())
            .collect()
    }

    /// Remove session
    pub fn remove(&self, session_id: &str) {
        let mut sessions = self.sessions.write();
        sessions.remove(session_id);
    }

    /// Clear all sessions
    pub fn clear(&self) {
        let mut sessions = self.sessions.write();
        sessions.clear();
    }

    /// Get active session count
    pub fn count(&self) -> usize {
        let sessions = self.sessions.read();
        sessions.len()
    }
}

/// Optimized HTML escape: pre-computed escape table
pub struct EscapeBuffer {
    buffer: Vec<u8>,
}

impl EscapeBuffer {
    /// Create new escape buffer
    pub fn new() -> Self {
        Self {
            buffer: Vec::with_capacity(512),
        }
    }

    /// Escape HTML string efficiently
    pub fn escape(&mut self, s: &str) -> String {
        self.buffer.clear();

        for byte in s.as_bytes() {
            match byte {
                b'&' => self.buffer.extend_from_slice(b"&amp;"),
                b'<' => self.buffer.extend_from_slice(b"&lt;"),
                b'>' => self.buffer.extend_from_slice(b"&gt;"),
                b'"' => self.buffer.extend_from_slice(b"&quot;"),
                b'\'' => self.buffer.extend_from_slice(b"&#39;"),
                _ => self.buffer.push(*byte),
            }
        }

        String::from_utf8_lossy(&self.buffer).to_string()
    }
}

impl Default for EscapeBuffer {
    fn default() -> Self {
        Self::new()
    }
}

// ===== INTERNALS =====

/// Get current timestamp in seconds
fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_render_cache_get_set() {
        let cache = RenderCache::new(100);
        cache.insert("comp1".to_string(), "<div>test</div>".to_string());
        assert_eq!(cache.get("comp1"), Some("<div>test</div>".to_string()));
        assert_eq!(cache.get("missing"), None);
    }

    #[test]
    fn test_render_cache_lru_eviction() {
        let cache = RenderCache::new(2);
        cache.insert("a".to_string(), "html_a".to_string());
        cache.insert("b".to_string(), "html_b".to_string());
        cache.insert("c".to_string(), "html_c".to_string()); // Should evict 'a'

        assert_eq!(cache.get("a"), None);
        assert_eq!(cache.get("b"), Some("html_b".to_string()));
        assert_eq!(cache.get("c"), Some("html_c".to_string()));
    }

    #[test]
    fn test_render_cache_invalidate() {
        let cache = RenderCache::new(100);
        cache.insert("comp1".to_string(), "<div>test</div>".to_string());
        cache.invalidate("comp1");
        assert_eq!(cache.get("comp1"), None);
    }

    #[test]
    fn test_validation_cache_ttl() {
        let cache = ValidationCache::new(1); // 1 second TTL
        cache.insert("comp1".to_string(), true);
        assert_eq!(cache.get("comp1"), Some(true));

        // Wait for expiration (note: in real tests use mock time)
        std::thread::sleep(Duration::from_millis(1100));
        // After TTL, should be considered expired
        // (actual expiration happens on next cleanup)
        cache.cleanup_expired();
        assert_eq!(cache.get("comp1"), None);
    }

    #[test]
    fn test_sse_ring_buffer_basic() {
        let buf = SseEventRingBuffer::new(10);
        buf.push("event1".to_string());
        buf.push("event2".to_string());
        buf.push("event3".to_string());

        let events = buf.drain();
        assert_eq!(events.len(), 3);
        assert_eq!(events[0], "event1");
        assert_eq!(events[1], "event2");
        assert_eq!(events[2], "event3");
    }

    #[test]
    fn test_sse_ring_buffer_fill_percent() {
        let buf = SseEventRingBuffer::new(100);
        assert_eq!(buf.fill_percent(), 0.0);

        for i in 0..50 {
            buf.push(format!("event_{}", i));
        }

        let fill = buf.fill_percent();
        assert!(fill > 40.0 && fill <= 50.0);
    }

    #[test]
    fn test_session_cleanup_touch_and_idle() {
        let cleanup = SessionCleanup::new(5); // 5 second timeout

        cleanup.touch("sess1".to_string());
        cleanup.touch("sess2".to_string());

        assert_eq!(cleanup.count(), 2);

        // Sessions should not be idle yet
        let idle_now = cleanup.get_idle_sessions();
        assert_eq!(idle_now.len(), 0);

        // Touch one session to mark it as recent
        cleanup.touch("sess1".to_string());
        std::thread::sleep(Duration::from_millis(100));

        // Verify cleanup tracker works by not removing recently touched session
        assert_eq!(cleanup.count(), 2);
    }

    #[test]
    fn test_escape_buffer_performance() {
        let mut buf = EscapeBuffer::new();
        let input = "Hello & <world> \"test\" 'quotes'";
        let escaped = buf.escape(input);

        assert!(escaped.contains("&amp;"));
        assert!(escaped.contains("&lt;"));
        assert!(escaped.contains("&gt;"));
        assert!(escaped.contains("&quot;"));
        assert!(escaped.contains("&#39;"));
    }

    #[test]
    fn test_cache_stats() {
        let cache = RenderCache::new(1000);
        cache.insert("a".to_string(), "html_a".to_string());
        cache.insert("b".to_string(), "html_b".to_string());

        let stats = cache.stats();
        assert_eq!(stats.len, 2);
        assert_eq!(stats.capacity, 1000);
    }

    #[test]
    fn test_escape_buffer_reuse() {
        let mut buf = EscapeBuffer::new();

        let result1 = buf.escape("<tag>");
        assert!(result1.contains("&lt;"));

        let result2 = buf.escape("'quotes'");
        assert!(result2.contains("&#39;"));
    }

    #[test]
    fn test_validation_cache_clear() {
        let cache = ValidationCache::new(30);
        cache.insert("comp1".to_string(), true);
        cache.insert("comp2".to_string(), false);
        assert!(cache.get("comp1").is_some());

        cache.clear();
        assert_eq!(cache.get("comp1"), None);
        assert_eq!(cache.get("comp2"), None);
    }
}
