use pyo3::prelude::*;

/// PyO3 module: siss_gatekeeper_py
/// Exposes Rust VisionAPI to Python

#[pymodule]
fn siss_gatekeeper_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", "0.1.0")?;
    // Submodules will be added in subsequent tasks
    Ok(())
}
