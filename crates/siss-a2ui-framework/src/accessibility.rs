use regex::Regex;

#[derive(Debug, Clone, PartialEq)]
pub struct AccessibilityViolation {
    pub rule: String,
    pub element: String,
    pub severity: String,
}

#[derive(Debug, Clone)]
pub struct AuditResult {
    pub passed: bool,
    pub violations: Vec<AccessibilityViolation>,
    pub wcag_level: String,
}

pub struct AccessibilityAuditor;

impl AccessibilityAuditor {
    pub fn audit_html(html: &str) -> AuditResult {
        let mut violations = Vec::new();

        // Rule 1: input_has_label
        Self::check_input_has_label(html, &mut violations);

        // Rule 2: modal_has_role
        Self::check_modal_has_role(html, &mut violations);

        // Rule 3: progress_has_aria
        Self::check_progress_has_aria(html, &mut violations);

        // Rule 4: breadcrumb_has_aria_label
        Self::check_breadcrumb_has_aria_label(html, &mut violations);

        // Rule 5: alert_has_role
        Self::check_alert_has_role(html, &mut violations);

        // Rule 6: checkbox_has_label
        Self::check_checkbox_has_label(html, &mut violations);

        // Rule 7: button_accessible_name
        Self::check_button_accessible_name(html, &mut violations);

        // Rule 8: link_has_text
        Self::check_link_has_text(html, &mut violations);

        // Rule 9: table_has_headers
        Self::check_table_has_headers(html, &mut violations);

        // Rule 10: interactive_not_div
        Self::check_interactive_not_div(html, &mut violations);

        let passed = violations.is_empty();
        let wcag_level = if passed {
            "AAA".to_string()
        } else {
            "AA".to_string()
        };

        AuditResult {
            passed,
            violations,
            wcag_level,
        }
    }

    fn check_input_has_label(html: &str, violations: &mut Vec<AccessibilityViolation>) {
        let input_re = Regex::new(r#"<input[^>]*id="([^"]*)"[^>]*/?>"#).unwrap();
        for cap in input_re.captures_iter(html) {
            let input_id = cap.get(1).map(|m| m.as_str()).unwrap_or("");
            let label_pattern = format!(r#"<label[^>]*for="{}"[^>]*>"#, regex::escape(input_id));
            if !Regex::new(&label_pattern).unwrap().is_match(html) {
                violations.push(AccessibilityViolation {
                    rule: "input_has_label".to_string(),
                    element: format!("input#{}", input_id),
                    severity: "error".to_string(),
                });
            }
        }
    }

    fn check_modal_has_role(html: &str, violations: &mut Vec<AccessibilityViolation>) {
        if html.contains("modal") && !html.contains(r#"role="dialog""#) {
            violations.push(AccessibilityViolation {
                rule: "modal_has_role".to_string(),
                element: "div.modal".to_string(),
                severity: "error".to_string(),
            });
        }
    }

    fn check_progress_has_aria(html: &str, violations: &mut Vec<AccessibilityViolation>) {
        if html.contains("<progress") {
            if !html.contains("aria-valuenow") || !html.contains("aria-valuemax") {
                violations.push(AccessibilityViolation {
                    rule: "progress_has_aria".to_string(),
                    element: "progress".to_string(),
                    severity: "error".to_string(),
                });
            }
        }
    }

    fn check_breadcrumb_has_aria_label(html: &str, violations: &mut Vec<AccessibilityViolation>) {
        if html.contains("breadcrumb") && !html.contains(r#"aria-label"#) {
            violations.push(AccessibilityViolation {
                rule: "breadcrumb_has_aria_label".to_string(),
                element: "nav.breadcrumb".to_string(),
                severity: "warning".to_string(),
            });
        }
    }

    fn check_alert_has_role(html: &str, violations: &mut Vec<AccessibilityViolation>) {
        if html.contains("alert") && !html.contains(r#"role="alert""#) {
            violations.push(AccessibilityViolation {
                rule: "alert_has_role".to_string(),
                element: "div.alert".to_string(),
                severity: "error".to_string(),
            });
        }
    }

    fn check_checkbox_has_label(html: &str, violations: &mut Vec<AccessibilityViolation>) {
        let checkbox_re = Regex::new(r#"<input[^>]*type="checkbox"[^>]*id="([^"]*)"[^>]*/?>"#).unwrap();
        for cap in checkbox_re.captures_iter(html) {
            let checkbox_id = cap.get(1).map(|m| m.as_str()).unwrap_or("");
            let label_pattern = format!(r#"<label[^>]*for="{}"[^>]*>"#, regex::escape(checkbox_id));
            if !Regex::new(&label_pattern).unwrap().is_match(html) {
                violations.push(AccessibilityViolation {
                    rule: "checkbox_has_label".to_string(),
                    element: format!("input[type=checkbox]#{}", checkbox_id),
                    severity: "error".to_string(),
                });
            }
        }
    }

    fn check_button_accessible_name(html: &str, violations: &mut Vec<AccessibilityViolation>) {
        let button_re = Regex::new(r#"<button[^>]*id="([^"]*)"[^>]*>([^<]*)<\/button>"#).unwrap();
        for cap in button_re.captures_iter(html) {
            let button_id = cap.get(1).map(|m| m.as_str()).unwrap_or("");
            let button_text = cap.get(2).map(|m| m.as_str()).unwrap_or("").trim();
            if button_text.is_empty() && !html.contains(&format!(r#"aria-label="{}"#, button_id)) {
                violations.push(AccessibilityViolation {
                    rule: "button_accessible_name".to_string(),
                    element: format!("button#{}", button_id),
                    severity: "error".to_string(),
                });
            }
        }
    }

    fn check_link_has_text(html: &str, violations: &mut Vec<AccessibilityViolation>) {
        let link_re = Regex::new(r#"<a[^>]*>([^<]*)<\/a>"#).unwrap();
        for cap in link_re.captures_iter(html) {
            let link_text = cap.get(1).map(|m| m.as_str()).unwrap_or("").trim();
            if link_text.is_empty() && !html.contains("aria-label") {
                violations.push(AccessibilityViolation {
                    rule: "link_has_text".to_string(),
                    element: "a".to_string(),
                    severity: "error".to_string(),
                });
            }
        }
    }

    fn check_table_has_headers(html: &str, violations: &mut Vec<AccessibilityViolation>) {
        if html.contains("<table") && !html.contains("<th") {
            violations.push(AccessibilityViolation {
                rule: "table_has_headers".to_string(),
                element: "table".to_string(),
                severity: "error".to_string(),
            });
        }
    }

    fn check_interactive_not_div(html: &str, violations: &mut Vec<AccessibilityViolation>) {
        if html.contains(r#"onclick="#) {
            violations.push(AccessibilityViolation {
                rule: "interactive_not_div".to_string(),
                element: "div[onclick]".to_string(),
                severity: "error".to_string(),
            });
        }
    }
}
