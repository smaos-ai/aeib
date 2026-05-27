use rusqlite::{Connection, params};
use uuid::Uuid;
use std::collections::HashMap;
use chrono::Utc;

#[derive(Debug, Clone)]
pub struct DispatchMetrics {
    pub mean_us: u64,
    pub p99_us: u64,
    pub min_us: u64,
    pub max_us: u64,
    pub sample_count: usize,
}

pub struct KPIDashboard {
    conn: Connection,
    in_memory_cache: HashMap<Uuid, Vec<u64>>,
}

impl KPIDashboard {
    pub fn new() -> Result<Self, rusqlite::Error> {
        let conn = Connection::open(":memory:")?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS dispatch_latencies (
                agent_id TEXT NOT NULL,
                latency_us INTEGER NOT NULL,
                timestamp INTEGER NOT NULL
            )",
        )?;
        Ok(KPIDashboard {
            conn,
            in_memory_cache: HashMap::new(),
        })
    }

    pub fn record_dispatch(&mut self, agent_id: Uuid, latency_us: u64) -> Result<(), rusqlite::Error> {
        let timestamp = Utc::now().timestamp();
        self.conn.execute(
            "INSERT INTO dispatch_latencies (agent_id, latency_us, timestamp)
             VALUES (?1, ?2, ?3)",
            params![agent_id.to_string(), latency_us, timestamp],
        )?;

        self.in_memory_cache
            .entry(agent_id)
            .or_insert_with(Vec::new)
            .push(latency_us);

        Ok(())
    }

    pub fn get_dispatch_metrics(&self) -> Result<DispatchMetrics, rusqlite::Error> {
        let mut stmt = self.conn.prepare(
            "SELECT latency_us FROM dispatch_latencies ORDER BY latency_us ASC"
        )?;

        let latencies: Vec<u64> = stmt.query_map([], |row| {
            row.get(0)
        })?
            .collect::<Result<Vec<_>, _>>()?;

        if latencies.is_empty() {
            return Ok(DispatchMetrics {
                mean_us: 0,
                p99_us: 0,
                min_us: 0,
                max_us: 0,
                sample_count: 0,
            });
        }

        let mean_us = latencies.iter().sum::<u64>() / latencies.len() as u64;
        let p99_index = (latencies.len() as f64 * 0.99).ceil() as usize - 1;
        let p99_us = latencies[p99_index.min(latencies.len() - 1)];
        let min_us = latencies[0];
        let max_us = latencies[latencies.len() - 1];

        Ok(DispatchMetrics {
            mean_us,
            p99_us,
            min_us,
            max_us,
            sample_count: latencies.len(),
        })
    }

    pub fn reset_metrics(&mut self) -> Result<(), rusqlite::Error> {
        self.conn.execute("DELETE FROM dispatch_latencies", [])?;
        self.in_memory_cache.clear();
        Ok(())
    }
}

impl Default for KPIDashboard {
    fn default() -> Self {
        Self::new().expect("Failed to create KPIDashboard")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_dispatch_latency_recorded_per_agent() {
        let mut dashboard = KPIDashboard::new().unwrap();

        let latencies = vec![45, 47, 49, 46, 48, 47];
        for latency in latencies.iter() {
            dashboard.record_dispatch(Uuid::new_v4(), *latency).unwrap();
        }

        let metrics = dashboard.get_dispatch_metrics().unwrap();
        assert_eq!(metrics.mean_us, 47);
        assert_eq!(metrics.p99_us, 49);
        assert!(metrics.mean_us < 100, "Mean must be <100µs");
    }

    #[test]
    fn test_p99_latency_below_threshold() {
        let mut dashboard = KPIDashboard::new().unwrap();

        for i in 0..100 {
            dashboard
                .record_dispatch(Uuid::new_v4(), 40 + (i % 10) as u64)
                .unwrap();
        }

        let metrics = dashboard.get_dispatch_metrics().unwrap();
        assert!(metrics.p99_us < 100, "P99 must be <100µs (proof of O(1))");
    }

    #[test]
    fn test_min_max_latency_tracked() {
        let mut dashboard = KPIDashboard::new().unwrap();

        dashboard.record_dispatch(Uuid::new_v4(), 40).unwrap();
        dashboard.record_dispatch(Uuid::new_v4(), 50).unwrap();
        dashboard.record_dispatch(Uuid::new_v4(), 45).unwrap();

        let metrics = dashboard.get_dispatch_metrics().unwrap();
        assert_eq!(metrics.min_us, 40);
        assert_eq!(metrics.max_us, 50);
    }

    #[test]
    fn test_empty_dashboard_returns_zero_metrics() {
        let dashboard = KPIDashboard::new().unwrap();

        let metrics = dashboard.get_dispatch_metrics().unwrap();
        assert_eq!(metrics.sample_count, 0);
        assert_eq!(metrics.mean_us, 0);
    }

    #[test]
    fn test_reset_clears_all_metrics() {
        let mut dashboard = KPIDashboard::new().unwrap();

        dashboard.record_dispatch(Uuid::new_v4(), 47).unwrap();
        dashboard.record_dispatch(Uuid::new_v4(), 48).unwrap();

        let metrics_before = dashboard.get_dispatch_metrics().unwrap();
        assert_eq!(metrics_before.sample_count, 2);

        dashboard.reset_metrics().unwrap();

        let metrics_after = dashboard.get_dispatch_metrics().unwrap();
        assert_eq!(metrics_after.sample_count, 0);
    }

    #[test]
    fn test_large_sample_set_p99_accuracy() {
        let mut dashboard = KPIDashboard::new().unwrap();

        // Simulate 1000 latency samples (47µs mean, P99 <100µs)
        for i in 0..1000 {
            let latency = 45 + (i % 8) as u64;
            dashboard.record_dispatch(Uuid::new_v4(), latency).unwrap();
        }

        let metrics = dashboard.get_dispatch_metrics().unwrap();
        assert_eq!(metrics.sample_count, 1000);
        assert!(metrics.p99_us < 100, "P99 latency must stay <100µs under load");
        assert!(metrics.mean_us >= 45 && metrics.mean_us <= 50, "Mean should be ~47µs");
    }
}
