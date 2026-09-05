use rusqlite::{Connection, Result as SqliteResult};
use std::path::PathBuf;

#[derive(Debug, Clone)]
pub struct MetricRow {
    pub timestamp: String,
    pub cpu_pct: f64,
    pub mem_mb: f64,
    pub test_duration_ms: u32,
    pub passed: u32,
    pub failed: u32,
}

pub struct MetricsDb {
    conn: Connection,
}

impl MetricsDb {
    pub fn new(db_path: Option<PathBuf>) -> SqliteResult<Self> {
        let path = db_path.unwrap_or_else(|| {
            PathBuf::from("/Users/andriileukhin/Documents/SovereignNexus/.claude/night_metrics.db")
        });

        let conn = Connection::open(path)?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS night_metrics (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                cpu_pct REAL NOT NULL,
                mem_mb REAL NOT NULL,
                test_duration_ms INTEGER NOT NULL,
                passed INTEGER NOT NULL,
                failed INTEGER NOT NULL
            )",
        )?;
        Ok(Self { conn })
    }

    pub fn record_run(
        &self,
        cpu_pct: f64,
        mem_mb: f64,
        test_duration_ms: u32,
        passed: u32,
        failed: u32,
    ) -> SqliteResult<()> {
        let timestamp = chrono::Utc::now().to_rfc3339();
        self.conn.execute(
            "INSERT INTO night_metrics (timestamp, cpu_pct, mem_mb, test_duration_ms, passed, failed)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            rusqlite::params![timestamp, cpu_pct, mem_mb, test_duration_ms, passed, failed],
        )?;
        Ok(())
    }

    pub fn last_50(&self) -> SqliteResult<Vec<MetricRow>> {
        let mut stmt = self.conn.prepare(
            "SELECT timestamp, cpu_pct, mem_mb, test_duration_ms, passed, failed
             FROM night_metrics ORDER BY timestamp DESC LIMIT 50",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok(MetricRow {
                timestamp: row.get(0)?,
                cpu_pct: row.get(1)?,
                mem_mb: row.get(2)?,
                test_duration_ms: row.get(3)?,
                passed: row.get(4)?,
                failed: row.get(5)?,
            })
        })?;

        let mut result = Vec::new();
        for row in rows {
            result.push(row?);
        }
        result.reverse();
        Ok(result)
    }

    pub fn stats(&self) -> SqliteResult<(f64, f64, f64)> {
        let mut stmt = self.conn.prepare(
            "SELECT AVG(cpu_pct), AVG(mem_mb), AVG(test_duration_ms) FROM night_metrics",
        )?;
        let (avg_cpu, avg_mem, avg_duration) =
            stmt.query_row([], |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)))?;
        Ok((avg_cpu, avg_mem, avg_duration))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::NamedTempFile;

    #[test]
    fn test_metrics_record_and_retrieve() {
        let temp_file = NamedTempFile::new().unwrap();
        let db = MetricsDb::new(Some(temp_file.path().to_path_buf())).unwrap();

        db.record_run(1.5, 100.0, 200, 25, 0).unwrap();
        db.record_run(2.0, 105.0, 210, 25, 0).unwrap();

        let rows = db.last_50().unwrap();
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0].cpu_pct, 1.5);
        assert_eq!(rows[1].cpu_pct, 2.0);
    }

    #[test]
    fn test_metrics_stats() {
        let temp_file = NamedTempFile::new().unwrap();
        let db = MetricsDb::new(Some(temp_file.path().to_path_buf())).unwrap();

        db.record_run(1.0, 100.0, 200, 25, 0).unwrap();
        db.record_run(3.0, 110.0, 210, 25, 0).unwrap();

        let (avg_cpu, avg_mem, _avg_duration) = db.stats().unwrap();
        assert!((avg_cpu - 2.0).abs() < 0.01);
        assert!((avg_mem - 105.0).abs() < 0.01);
    }
}
