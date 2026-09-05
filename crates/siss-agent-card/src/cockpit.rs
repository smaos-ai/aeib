use axum::http::StatusCode;
use axum::response::IntoResponse;

/// GET /cockpit
/// Serves the minimal AoE cockpit panel HTML (static file)
/// The panel consumes SSE events from /events and displays recovery status live
pub async fn cockpit_handler() -> impl IntoResponse {
    const COCKPIT_HTML: &str = include_str!("../static/cockpit.html");
    (
        StatusCode::OK,
        [("content-type", "text/html")],
        COCKPIT_HTML,
    )
}

#[cfg(test)]
mod tests {
    #[test]
    fn test_cockpit_html_included() {
        let html = include_str!("../static/cockpit.html");
        assert!(html.contains("SMAOS"));
        assert!(html.contains("/events"));
    }
}
