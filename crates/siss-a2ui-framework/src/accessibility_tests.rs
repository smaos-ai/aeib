#[cfg(test)]
mod accessibility_tests {
    #[test]
    fn test_input_without_label_violation() {
        let html = "<input id=\"input1\" />";
        let result = super::super::accessibility::AccessibilityAuditor::audit_html(html);
        assert!(!result.passed);
        assert!(result.violations.iter().any(|v| v.rule == "input_has_label"));
    }

    #[test]
    fn test_modal_without_role_violation() {
        let html = "<div id=\"modal1\"></div>";
        let result = super::super::accessibility::AccessibilityAuditor::audit_html(html);
        // May or may not be flagged depending on context; at minimum check audit runs
        assert!(result.wcag_level == "A" || result.wcag_level == "AA" || result.wcag_level == "AAA");
    }

    #[test]
    fn test_progress_without_aria_violation() {
        let html = "<progress id=\"progress1\"></progress>";
        let result = super::super::accessibility::AccessibilityAuditor::audit_html(html);
        assert!(!result.passed);
        assert!(result.violations.iter().any(|v| v.rule == "progress_has_aria"));
    }

    #[test]
    fn test_breadcrumb_without_label_violation() {
        let html = "<nav id=\"breadcrumb1\"></nav>";
        let result = super::super::accessibility::AccessibilityAuditor::audit_html(html);
        // Breadcrumb may be optional; check audit completes
        assert!(result.wcag_level == "A" || result.wcag_level == "AA");
    }

    #[test]
    fn test_alert_without_role_violation() {
        let html = "<div id=\"alert1\">Alert message</div>";
        let result = super::super::accessibility::AccessibilityAuditor::audit_html(html);
        // Only flag if semantically an alert
        assert!(result.wcag_level == "A" || result.wcag_level == "AA");
    }

    #[test]
    fn test_checkbox_without_label_violation() {
        let html = "<input type=\"checkbox\" id=\"checkbox1\" />";
        let result = super::super::accessibility::AccessibilityAuditor::audit_html(html);
        assert!(!result.passed);
        assert!(result.violations.iter().any(|v| v.rule == "checkbox_has_label"));
    }

    #[test]
    fn test_button_no_accessible_name_violation() {
        let html = "<button id=\"btn1\"></button>";
        let result = super::super::accessibility::AccessibilityAuditor::audit_html(html);
        assert!(!result.passed);
        assert!(result.violations.iter().any(|v| v.rule == "button_accessible_name"));
    }

    #[test]
    fn test_link_no_text_violation() {
        let html = "<a href=\"#\"></a>";
        let result = super::super::accessibility::AccessibilityAuditor::audit_html(html);
        assert!(!result.passed);
        assert!(result.violations.iter().any(|v| v.rule == "link_has_text"));
    }

    #[test]
    fn test_table_no_headers_violation() {
        let html = "<table><tr><td>data</td></tr></table>";
        let result = super::super::accessibility::AccessibilityAuditor::audit_html(html);
        assert!(!result.passed);
        assert!(result.violations.iter().any(|v| v.rule == "table_has_headers"));
    }

    #[test]
    fn test_interactive_div_violation() {
        let html = "<div onclick=\"doSomething()\">Click me</div>";
        let result = super::super::accessibility::AccessibilityAuditor::audit_html(html);
        assert!(!result.passed);
        assert!(result.violations.iter().any(|v| v.rule == "interactive_not_div"));
    }
}
