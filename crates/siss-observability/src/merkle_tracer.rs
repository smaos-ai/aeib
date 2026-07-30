use crate::{Metrics, ObservabilityError, Result};
use dashmap::DashMap;
use sha2::{Sha256, Digest};
use std::sync::Arc;
use std::sync::Mutex;
use uuid::Uuid;
use std::time::SystemTime;

#[derive(Debug, Clone)]
pub struct TraceSpan {
    pub span_id: Uuid,
    pub parent_id: Option<Uuid>,
    pub merkle_hash: [u8; 32],
    pub metrics: Arc<Metrics>,
    pub start_time: SystemTime,
    pub end_time: Option<SystemTime>,
}

impl TraceSpan {
    pub fn new(span_id: Uuid, parent_id: Option<Uuid>) -> Self {
        let metrics = Arc::new(Metrics::new());
        let hash = Self::compute_hash(&span_id, parent_id.as_ref(), &[0u8; 32]);
        Self {
            span_id,
            parent_id,
            merkle_hash: hash,
            metrics,
            start_time: SystemTime::now(),
            end_time: None,
        }
    }

    pub fn compute_hash(span_id: &Uuid, parent_id: Option<&Uuid>, previous_hash: &[u8; 32]) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(span_id.as_bytes());
        if let Some(pid) = parent_id {
            hasher.update(pid.as_bytes());
        }
        hasher.update(previous_hash);
        let result = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&result[..32]);
        hash
    }

    pub fn complete(&mut self) {
        self.end_time = Some(SystemTime::now());
    }

    pub fn with_metrics(&mut self, metrics: Metrics) {
        *Arc::get_mut(&mut self.metrics).unwrap() = metrics;
    }
}

pub struct MerkleTracer {
    traces: Arc<DashMap<Uuid, TraceSpan>>,
    merkle_root: Arc<Mutex<[u8; 32]>>,
    span_order: Arc<Mutex<Vec<Uuid>>>,
}

impl MerkleTracer {
    pub fn new() -> Self {
        Self {
            traces: Arc::new(DashMap::new()),
            merkle_root: Arc::new(Mutex::new([0u8; 32])),
            span_order: Arc::new(Mutex::new(Vec::new())),
        }
    }

    pub async fn record_span(&self, mut span: TraceSpan) -> Result<()> {
        let span_id = span.span_id;

        // Compute merkle hash based on parent linkage
        if let Some(parent_id) = span.parent_id {
            let previous_hash = self.traces
                .get(&parent_id)
                .map(|s| s.merkle_hash)
                .ok_or(ObservabilityError::TraceNotFound(parent_id.to_string()))?;
            span.merkle_hash = TraceSpan::compute_hash(&span_id, Some(&parent_id), &previous_hash);
        } else {
            // For root spans, use current merkle_root as the previous_hash
            let merkle_root = self.merkle_root.lock().unwrap();
            span.merkle_hash = TraceSpan::compute_hash(&span_id, None, &*merkle_root);
        }

        self.traces.insert(span_id, span.clone());

        // Update global order
        self.span_order.lock().unwrap().push(span_id);

        // Update merkle root for root-level spans only
        if span.parent_id.is_none() {
            let mut root = self.merkle_root.lock().unwrap();
            root.copy_from_slice(&span.merkle_hash);
        }

        Ok(())
    }

    pub fn get_span(&self, span_id: Uuid) -> Option<TraceSpan> {
        self.traces.get(&span_id).map(|s| s.clone())
    }

    pub fn get_trace_chain(&self, span_id: Uuid) -> Result<Vec<TraceSpan>> {
        let mut chain = Vec::new();
        let mut current_id = Some(span_id);

        while let Some(id) = current_id {
            let span = self.traces
                .get(&id)
                .ok_or(ObservabilityError::TraceNotFound(id.to_string()))?
                .clone();
            current_id = span.parent_id;
            chain.push(span);
        }

        chain.reverse();
        Ok(chain)
    }

    pub async fn verify_trace_integrity(&self) -> Result<bool> {
        let root = *self.merkle_root.lock().unwrap();
        let order = self.span_order.lock().unwrap();

        let mut computed_root = [0u8; 32];
        for span_id in order.iter() {
            if let Some(span) = self.traces.get(span_id) {
                let mut hasher = Sha256::new();
                hasher.update(&computed_root);
                hasher.update(span.merkle_hash);
                let result = hasher.finalize();
                computed_root.copy_from_slice(&result[..32]);
            }
        }

        Ok(computed_root == root)
    }

    pub fn get_merkle_root(&self) -> [u8; 32] {
        *self.merkle_root.lock().unwrap()
    }

    pub fn span_count(&self) -> usize {
        self.traces.len()
    }

    pub fn get_all_spans(&self) -> Vec<TraceSpan> {
        self.traces.iter().map(|entry| entry.value().clone()).collect()
    }

    pub fn detect_tampering(&self) -> Result<bool> {
        let order = self.span_order.lock().unwrap();
        let mut previous_hash = [0u8; 32];

        for span_id in order.iter() {
            if let Some(span) = self.traces.get(span_id) {
                // Verify parent linkage
                if let Some(parent_id) = span.parent_id {
                    if !self.traces.contains_key(&parent_id) {
                        return Ok(true); // Tampering detected
                    }
                    // For child spans, verify against parent's hash
                    let parent_hash = self.traces
                        .get(&parent_id)
                        .map(|s| s.merkle_hash)
                        .ok_or(ObservabilityError::IntegrityCheckFailed("Parent not found".into()))?;
                    let expected_hash = TraceSpan::compute_hash(&span_id, Some(&parent_id), &parent_hash);
                    if expected_hash != span.merkle_hash {
                        return Ok(true);
                    }
                } else {
                    // For root spans, verify against accumulated previous_hash
                    let expected_hash = TraceSpan::compute_hash(&span_id, None, &previous_hash);
                    if expected_hash != span.merkle_hash {
                        return Ok(true);
                    }
                    previous_hash = span.merkle_hash;
                }
            }
        }

        Ok(false)
    }
}

impl Default for MerkleTracer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_record_single_span() {
        let tracer = MerkleTracer::new();
        let span = TraceSpan::new(Uuid::new_v4(), None);

        assert!(tracer.record_span(span.clone()).await.is_ok());
        assert_eq!(tracer.span_count(), 1);
    }

    #[tokio::test]
    async fn test_parent_child_linkage() {
        let tracer = MerkleTracer::new();
        let parent_id = Uuid::new_v4();
        let parent = TraceSpan::new(parent_id, None);

        tracer.record_span(parent.clone()).await.unwrap();

        let child_id = Uuid::new_v4();
        let child = TraceSpan::new(child_id, Some(parent_id));

        assert!(tracer.record_span(child.clone()).await.is_ok());
        assert_eq!(tracer.span_count(), 2);
    }

    #[tokio::test]
    async fn test_get_trace_chain() {
        let tracer = MerkleTracer::new();

        let grandparent_id = Uuid::new_v4();
        let grandparent = TraceSpan::new(grandparent_id, None);
        tracer.record_span(grandparent.clone()).await.unwrap();

        let parent_id = Uuid::new_v4();
        let parent = TraceSpan::new(parent_id, Some(grandparent_id));
        tracer.record_span(parent.clone()).await.unwrap();

        let child_id = Uuid::new_v4();
        let child = TraceSpan::new(child_id, Some(parent_id));
        tracer.record_span(child.clone()).await.unwrap();

        let chain = tracer.get_trace_chain(child_id).unwrap();
        assert_eq!(chain.len(), 3);
        assert_eq!(chain[0].span_id, grandparent_id);
        assert_eq!(chain[1].span_id, parent_id);
        assert_eq!(chain[2].span_id, child_id);
    }

    #[tokio::test]
    async fn test_verify_integrity_valid() {
        let tracer = MerkleTracer::new();

        let span1 = TraceSpan::new(Uuid::new_v4(), None);
        tracer.record_span(span1.clone()).await.unwrap();

        let is_valid = tracer.verify_trace_integrity().await.unwrap();
        assert!(is_valid);
    }

    #[tokio::test]
    async fn test_merkle_hash_computation() {
        let span_id = Uuid::new_v4();
        let parent_id = Uuid::new_v4();
        let previous_hash = [1u8; 32];

        let hash1 = TraceSpan::compute_hash(&span_id, Some(&parent_id), &previous_hash);
        let hash2 = TraceSpan::compute_hash(&span_id, Some(&parent_id), &previous_hash);

        assert_eq!(hash1, hash2);
    }

    #[tokio::test]
    async fn test_get_span() {
        let tracer = MerkleTracer::new();
        let span_id = Uuid::new_v4();
        let span = TraceSpan::new(span_id, None);

        tracer.record_span(span.clone()).await.unwrap();

        let retrieved = tracer.get_span(span_id);
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().span_id, span_id);
    }

    #[tokio::test]
    async fn test_detect_tampering_clean() {
        let tracer = MerkleTracer::new();
        let span = TraceSpan::new(Uuid::new_v4(), None);
        tracer.record_span(span).await.unwrap();

        let is_tampered = tracer.detect_tampering().unwrap();
        assert!(!is_tampered);
    }

    #[tokio::test]
    async fn test_merkle_root_changes() {
        let tracer = MerkleTracer::new();
        let root1 = tracer.get_merkle_root();

        let span = TraceSpan::new(Uuid::new_v4(), None);
        tracer.record_span(span).await.unwrap();

        let root2 = tracer.get_merkle_root();
        assert_ne!(root1, root2);
    }

    #[tokio::test]
    async fn test_multiple_children_same_parent() {
        let tracer = MerkleTracer::new();
        let parent_id = Uuid::new_v4();
        let parent = TraceSpan::new(parent_id, None);
        tracer.record_span(parent).await.unwrap();

        let child1 = TraceSpan::new(Uuid::new_v4(), Some(parent_id));
        let child2 = TraceSpan::new(Uuid::new_v4(), Some(parent_id));

        tracer.record_span(child1).await.unwrap();
        tracer.record_span(child2).await.unwrap();

        assert_eq!(tracer.span_count(), 3);
    }
}
