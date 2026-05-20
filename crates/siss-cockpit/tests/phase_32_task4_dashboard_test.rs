use siss_cockpit::handlers::dashboard::DASHBOARD_HTML;

/// Test 1: HTML is non-empty and has correct doctype/content markers
#[test]
fn test_dashboard_serves_html() {
    // The constant is the same string the handler returns as Html<&'static str>.
    // A 200 response with text/html is guaranteed by axum::response::Html
    // when the handler returns Html(DASHBOARD_HTML).
    assert!(!DASHBOARD_HTML.is_empty(), "dashboard HTML must not be empty");
    assert!(
        DASHBOARD_HTML.contains("<!DOCTYPE html>"),
        "must be a full HTML document"
    );
}

/// Test 2: SSE connection is wired up
#[test]
fn test_dashboard_contains_sse_connection() {
    assert!(
        DASHBOARD_HTML.contains("EventSource"),
        "must use EventSource API"
    );
    assert!(
        DASHBOARD_HTML.contains("/api/agents/stream"),
        "must connect to the SSE stream endpoint"
    );
}

/// Test 3: Agent control keywords are present
#[test]
fn test_dashboard_contains_agent_controls() {
    assert!(
        DASHBOARD_HTML.contains("pause"),
        "must contain pause control"
    );
    assert!(
        DASHBOARD_HTML.contains("resume"),
        "must contain resume control"
    );
    assert!(
        DASHBOARD_HTML.contains("abort"),
        "must contain abort control"
    );
}
