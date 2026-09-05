use axum::response::Html;

/// Static dashboard HTML embedded at compile time.
/// Path is relative to this source file: ../../static/dashboard.html
pub const DASHBOARD_HTML: &str = include_str!("../../static/dashboard.html");

pub async fn dashboard() -> Html<&'static str> {
    Html(DASHBOARD_HTML)
}
