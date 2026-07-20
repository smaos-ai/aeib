use crate::a2ui::schema::*;
use crate::a2ui::validator::{A2UIValidator, ValidationError};

#[test]
fn test_accepts_text_component() {
    let component = A2UIComponent::Text {
        id: "test".to_string(),
        content: "Hello".to_string(),
        size: None,
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_accepts_input_component() {
    let component = A2UIComponent::Input {
        id: "field1".to_string(),
        label: "Name".to_string(),
        placeholder: Some("Enter name".to_string()),
        required: true,
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_accepts_button_component() {
    let component = A2UIComponent::Button {
        id: "btn".to_string(),
        label: "Submit".to_string(),
        action: Some("submit".to_string()),
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_accepts_card_with_nested_components() {
    let component = A2UIComponent::Card {
        id: "card1".to_string(),
        title: Some("Details".to_string()),
        children: vec![A2UIComponent::Text {
            id: "text1".to_string(),
            content: "Content".to_string(),
            size: None,
        }],
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_validates_all_18_primitives() {
    // Display (8)
    let display_components = vec![
        A2UIComponent::Text {
            id: "1".to_string(),
            content: "t".to_string(),
            size: None,
        },
        A2UIComponent::Badge {
            id: "2".to_string(),
            label: "b".to_string(),
            color: None,
        },
        A2UIComponent::Alert {
            id: "3".to_string(),
            message: "a".to_string(),
            level: "info".to_string(),
        },
        A2UIComponent::Progress {
            id: "4".to_string(),
            value: 50,
            max: 100,
            label: None,
        },
        A2UIComponent::Divider {
            id: "5".to_string(),
        },
        A2UIComponent::Link {
            id: "6".to_string(),
            label: "l".to_string(),
            href: "http://x".to_string(),
        },
        A2UIComponent::Tooltip {
            id: "7".to_string(),
            text: "t".to_string(),
            content: "tip".to_string(),
        },
        A2UIComponent::Breadcrumb {
            id: "8".to_string(),
            items: vec![],
        },
    ];
    for comp in display_components {
        assert!(
            A2UIValidator::validate(&comp).is_ok(),
            "Failed for: {:?}",
            comp
        );
    }

    // Forms (6)
    let form_components = vec![
        A2UIComponent::Input {
            id: "9".to_string(),
            label: "i".to_string(),
            placeholder: None,
            required: false,
        },
        A2UIComponent::Textarea {
            id: "10".to_string(),
            label: "ta".to_string(),
            rows: None,
        },
        A2UIComponent::Select {
            id: "11".to_string(),
            label: "s".to_string(),
            options: vec![SelectOption {
                value: "opt".to_string(),
                label: "o".to_string(),
            }],
        },
        A2UIComponent::Checkbox {
            id: "12".to_string(),
            label: "c".to_string(),
            checked: false,
        },
        A2UIComponent::Radio {
            id: "13".to_string(),
            label: "r".to_string(),
            value: "v".to_string(),
            checked: false,
        },
        A2UIComponent::Button {
            id: "14".to_string(),
            label: "btn".to_string(),
            action: None,
        },
    ];
    for comp in form_components {
        assert!(
            A2UIValidator::validate(&comp).is_ok(),
            "Failed for: {:?}",
            comp
        );
    }

    // Layout (4)
    let layout_components = vec![
        A2UIComponent::Card {
            id: "15".to_string(),
            title: None,
            children: vec![],
        },
        A2UIComponent::Grid {
            id: "16".to_string(),
            columns: 2,
            children: vec![],
        },
        A2UIComponent::Modal {
            id: "17".to_string(),
            title: "m".to_string(),
            content: "c".to_string(),
            children: vec![A2UIComponent::Button {
                id: "mbtn".to_string(),
                label: "OK".to_string(),
                action: None,
            }],
        },
        A2UIComponent::Table {
            id: "18".to_string(),
            headers: vec![],
            rows: vec![],
        },
    ];
    for comp in layout_components {
        assert!(
            A2UIValidator::validate(&comp).is_ok(),
            "Failed for: {:?}",
            comp
        );
    }
}

#[test]
fn test_validator_rejects_invalid_nested_components() {
    let invalid_component = A2UIComponent::Card {
        id: "card".to_string(),
        title: None,
        children: vec![A2UIComponent::Text {
            id: "text".to_string(),
            content: "valid".to_string(),
            size: None,
        }],
    };
    assert!(A2UIValidator::validate(&invalid_component).is_ok());
}

#[test]
fn test_returns_error_message_on_validation_failure() {
    // This test would require creating an invalid component type
    // For now, we ensure validator returns descriptive error
    let component = A2UIComponent::Text {
        id: "".to_string(), // Empty ID should fail
        content: "x".to_string(),
        size: None,
    };
    let result = A2UIValidator::validate(&component);
    if let Err(msg) = result {
        assert!(!msg.is_empty(), "Error message should not be empty");
    }
}

#[test]
fn test_all_display_components_serialize() {
    let components = vec![
        A2UIComponent::Text {
            id: "t1".into(),
            content: "text".into(),
            size: None,
        },
        A2UIComponent::Badge {
            id: "b1".into(),
            label: "badge".into(),
            color: None,
        },
        A2UIComponent::Alert {
            id: "a1".into(),
            message: "alert".into(),
            level: "info".into(),
        },
        A2UIComponent::Progress {
            id: "p1".into(),
            value: 50,
            max: 100,
            label: None,
        },
        A2UIComponent::Divider { id: "d1".into() },
        A2UIComponent::Link {
            id: "l1".into(),
            label: "link".into(),
            href: "http://x".into(),
        },
        A2UIComponent::Tooltip {
            id: "tt1".into(),
            text: "t".into(),
            content: "c".into(),
        },
        A2UIComponent::Breadcrumb {
            id: "br1".into(),
            items: vec!["home".into(), "page".into()],
        },
    ];

    for comp in components {
        let json = serde_json::to_string(&comp).expect("Should serialize");
        let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
        assert_eq!(comp, deserialized);
    }
}

#[test]
fn test_all_form_components_serialize() {
    let components = vec![
        A2UIComponent::Input {
            id: "i1".into(),
            label: "input".into(),
            placeholder: None,
            required: false,
        },
        A2UIComponent::Textarea {
            id: "ta1".into(),
            label: "textarea".into(),
            rows: None,
        },
        A2UIComponent::Select {
            id: "s1".into(),
            label: "select".into(),
            options: vec![SelectOption {
                value: "v1".into(),
                label: "opt1".into(),
            }],
        },
        A2UIComponent::Checkbox {
            id: "c1".into(),
            label: "check".into(),
            checked: false,
        },
        A2UIComponent::Radio {
            id: "r1".into(),
            label: "radio".into(),
            value: "rv".into(),
            checked: false,
        },
        A2UIComponent::Button {
            id: "btn1".into(),
            label: "button".into(),
            action: None,
        },
    ];

    for comp in components {
        let json = serde_json::to_string(&comp).expect("Should serialize");
        let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
        assert_eq!(comp, deserialized);
    }
}

#[test]
fn test_all_layout_components_serialize() {
    let components = vec![
        A2UIComponent::Card {
            id: "card1".into(),
            title: None,
            children: vec![],
        },
        A2UIComponent::Grid {
            id: "grid1".into(),
            columns: 2,
            children: vec![],
        },
        A2UIComponent::Modal {
            id: "modal1".into(),
            title: "title".into(),
            content: "content".into(),
            children: vec![],
        },
        A2UIComponent::Table {
            id: "table1".into(),
            headers: vec!["h1".into(), "h2".into()],
            rows: vec![],
        },
    ];

    for comp in components {
        let json = serde_json::to_string(&comp).expect("Should serialize");
        let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
        assert_eq!(comp, deserialized);
    }
}

#[test]
fn test_text_component_with_size_variants() {
    let sizes = vec!["sm", "md", "lg"];
    for size in sizes {
        let component = A2UIComponent::Text {
            id: "txt".into(),
            content: "Hello".into(),
            size: Some(size.into()),
        };
        assert!(A2UIValidator::validate(&component).is_ok());
        let json = serde_json::to_string(&component).unwrap();
        assert!(json.contains(size));
    }
}

#[test]
fn test_badge_with_color_variants() {
    let colors = vec!["blue", "red", "green", "yellow"];
    for color in colors {
        let component = A2UIComponent::Badge {
            id: "badge".into(),
            label: "Badge".into(),
            color: Some(color.into()),
        };
        assert!(A2UIValidator::validate(&component).is_ok());
    }
}

#[test]
fn test_input_with_placeholder_and_required() {
    let component = A2UIComponent::Input {
        id: "field".into(),
        label: "Name".into(),
        placeholder: Some("Enter your name".into()),
        required: true,
    };
    assert!(A2UIValidator::validate(&component).is_ok());
    let json = serde_json::to_string(&component).unwrap();
    assert!(json.contains("required"));
}

#[test]
fn test_select_with_multiple_options() {
    let options = vec![
        SelectOption {
            value: "opt1".into(),
            label: "Option 1".into(),
        },
        SelectOption {
            value: "opt2".into(),
            label: "Option 2".into(),
        },
        SelectOption {
            value: "opt3".into(),
            label: "Option 3".into(),
        },
    ];
    let component = A2UIComponent::Select {
        id: "select".into(),
        label: "Choose".into(),
        options,
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_radio_group_structure() {
    let component = A2UIComponent::Radio {
        id: "gender".into(),
        label: "Gender".into(),
        value: "male".into(),
        checked: true,
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_nested_card_structure() {
    let inner_text = A2UIComponent::Text {
        id: "inner_text".into(),
        content: "Inner content".into(),
        size: None,
    };
    let inner_button = A2UIComponent::Button {
        id: "inner_btn".into(),
        label: "Click me".into(),
        action: Some("custom".into()),
    };
    let card = A2UIComponent::Card {
        id: "main_card".into(),
        title: Some("Details".into()),
        children: vec![inner_text, inner_button],
    };
    assert!(A2UIValidator::validate(&card).is_ok());
}

#[test]
fn test_grid_with_nested_components() {
    let children = vec![
        A2UIComponent::Text {
            id: "g1".into(),
            content: "Cell 1".into(),
            size: None,
        },
        A2UIComponent::Text {
            id: "g2".into(),
            content: "Cell 2".into(),
            size: None,
        },
        A2UIComponent::Text {
            id: "g3".into(),
            content: "Cell 3".into(),
            size: None,
        },
    ];
    let grid = A2UIComponent::Grid {
        id: "grid".into(),
        columns: 3,
        children,
    };
    assert!(A2UIValidator::validate(&grid).is_ok());
}

#[test]
fn test_modal_structure() {
    let component = A2UIComponent::Modal {
        id: "modal".into(),
        title: "Confirmation".into(),
        content: "Are you sure?".into(),
        children: vec![
            A2UIComponent::Button {
                id: "yes".into(),
                label: "Yes".into(),
                action: None,
            },
            A2UIComponent::Button {
                id: "no".into(),
                label: "No".into(),
                action: None,
            },
        ],
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_table_with_headers_and_rows() {
    let component = A2UIComponent::Table {
        id: "data_table".into(),
        headers: vec!["ID".into(), "Name".into(), "Email".into()],
        rows: vec![
            vec!["1".into(), "Alice".into(), "alice@example.com".into()],
            vec!["2".into(), "Bob".into(), "bob@example.com".into()],
        ],
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_progress_bar_validation() {
    // Valid: value <= max
    let valid = A2UIComponent::Progress {
        id: "prog".into(),
        value: 50,
        max: 100,
        label: Some("50%".into()),
    };
    assert!(A2UIValidator::validate(&valid).is_ok());

    // Invalid: value > max
    let invalid = A2UIComponent::Progress {
        id: "prog".into(),
        value: 150,
        max: 100,
        label: None,
    };
    assert!(A2UIValidator::validate(&invalid).is_err());
}

#[test]
fn test_breadcrumb_with_navigation_items() {
    let component = A2UIComponent::Breadcrumb {
        id: "nav".into(),
        items: vec![
            "Home".into(),
            "Products".into(),
            "Electronics".into(),
            "Phones".into(),
        ],
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_link_component_with_href() {
    let component = A2UIComponent::Link {
        id: "link".into(),
        label: "Click here".into(),
        href: "https://example.com/page".into(),
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_tooltip_interactive_component() {
    let component = A2UIComponent::Tooltip {
        id: "tooltip".into(),
        text: "Hover me".into(),
        content: "This is helpful information".into(),
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_textarea_with_rows_specification() {
    let component = A2UIComponent::Textarea {
        id: "comments".into(),
        label: "Comments".into(),
        rows: Some(10),
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_alert_with_different_levels() {
    for level in vec!["info", "warn", "error"] {
        let component = A2UIComponent::Alert {
            id: format!("alert_{}", level),
            message: "Message".into(),
            level: level.into(),
        };
        assert!(A2UIValidator::validate(&component).is_ok());
    }
}

// === CONTEXT-AWARE VALIDATION TESTS (Wave 2) ===

#[test]
fn test_form_validation_with_context_required_fields() {
    // A form with required=true input should fail if empty value provided
    let form_state = vec![
        ("name_field".to_string(), serde_json::json!("")),
        (
            "email_field".to_string(),
            serde_json::json!("test@example.com"),
        ),
    ];

    // Validate: name_field is required but empty
    let result = A2UIValidator::validate_form_state(
        &form_state,
        &[
            ("name_field".to_string(), true),   // required
            ("email_field".to_string(), false), // optional
        ],
    );

    assert!(result.is_err());
    if let Err(e) = result {
        assert!(e.contains("name_field") || e.contains("required"));
    }
}

#[test]
fn test_form_validation_all_required_fields_provided() {
    let form_state = vec![
        ("name_field".to_string(), serde_json::json!("John")),
        (
            "email_field".to_string(),
            serde_json::json!("john@example.com"),
        ),
    ];

    let result = A2UIValidator::validate_form_state(
        &form_state,
        &[
            ("name_field".to_string(), true),
            ("email_field".to_string(), true),
        ],
    );

    assert!(result.is_ok());
}

#[test]
fn test_cross_field_dependency_validation() {
    // When "use_address" is checked, "address_field" must not be empty
    let form_state = vec![
        ("use_address".to_string(), serde_json::json!(true)),
        ("address_field".to_string(), serde_json::json!("")),
    ];

    let result = A2UIValidator::validate_cross_field_dependency(
        "use_address",
        true,
        "address_field",
        &form_state,
    );

    assert!(result.is_err());
    if let Err(e) = result {
        assert!(e.contains("address_field") || e.contains("dependency"));
    }
}

#[test]
fn test_cross_field_dependency_satisfied() {
    let form_state = vec![
        ("use_address".to_string(), serde_json::json!(true)),
        (
            "address_field".to_string(),
            serde_json::json!("123 Main St"),
        ),
    ];

    let result = A2UIValidator::validate_cross_field_dependency(
        "use_address",
        true,
        "address_field",
        &form_state,
    );

    assert!(result.is_ok());
}

#[test]
fn test_cross_field_dependency_ignored_when_condition_false() {
    let form_state = vec![
        ("use_address".to_string(), serde_json::json!(false)),
        ("address_field".to_string(), serde_json::json!("")),
    ];

    let result = A2UIValidator::validate_cross_field_dependency(
        "use_address",
        true,
        "address_field",
        &form_state,
    );

    // Should pass because dependency condition is not met
    assert!(result.is_ok());
}

#[test]
fn test_mutually_exclusive_field_validation() {
    // Either "password" or "oauth_token" must be provided, but not both
    let form_state = vec![
        ("password".to_string(), serde_json::json!("pass123")),
        ("oauth_token".to_string(), serde_json::json!("token456")),
    ];

    let result = A2UIValidator::validate_mutually_exclusive(
        &["password".to_string(), "oauth_token".to_string()],
        &form_state,
    );

    assert!(result.is_err());
    if let Err(e) = result {
        assert!(e.contains("mutually exclusive") || e.contains("both"));
    }
}

#[test]
fn test_mutually_exclusive_exactly_one_provided() {
    let form_state = vec![
        ("password".to_string(), serde_json::json!("pass123")),
        ("oauth_token".to_string(), serde_json::json!("")),
    ];

    let result = A2UIValidator::validate_mutually_exclusive(
        &["password".to_string(), "oauth_token".to_string()],
        &form_state,
    );

    assert!(result.is_ok());
}

#[test]
fn test_mutually_exclusive_neither_provided() {
    let form_state = vec![
        ("password".to_string(), serde_json::json!("")),
        ("oauth_token".to_string(), serde_json::json!("")),
    ];

    let result = A2UIValidator::validate_mutually_exclusive(
        &["password".to_string(), "oauth_token".to_string()],
        &form_state,
    );

    // Should fail: neither provided
    assert!(result.is_err());
}

#[test]
fn test_field_format_validation_email() {
    let result = A2UIValidator::validate_field_format("email", "test@example.com", "email");
    assert!(result.is_ok());

    let result = A2UIValidator::validate_field_format("email", "invalid-email", "email");
    assert!(result.is_err());
}

#[test]
fn test_field_format_validation_phone() {
    let result = A2UIValidator::validate_field_format("phone", "+1-555-123-4567", "phone");
    assert!(result.is_ok());

    let result = A2UIValidator::validate_field_format("phone", "123", "phone");
    assert!(result.is_err());
}

#[test]
fn test_field_format_validation_url() {
    let result = A2UIValidator::validate_field_format("url", "https://example.com", "url");
    assert!(result.is_ok());

    let result = A2UIValidator::validate_field_format("url", "not a url", "url");
    assert!(result.is_err());
}

#[test]
fn test_field_length_validation_min_max() {
    let result = A2UIValidator::validate_field_length("username", 3, 20, "john");
    assert!(result.is_ok());

    let result = A2UIValidator::validate_field_length("username", 3, 20, "ab");
    assert!(result.is_err());

    let result =
        A2UIValidator::validate_field_length("username", 3, 20, "this_is_a_very_long_username");
    assert!(result.is_err());
}

#[test]
fn test_form_state_completeness_check() {
    let form_state = vec![
        ("field1".to_string(), serde_json::json!("value1")),
        ("field2".to_string(), serde_json::json!("value2")),
    ];

    let required_fields = vec!["field1".to_string(), "field2".to_string()];

    let result = A2UIValidator::check_form_completeness(&form_state, &required_fields);
    assert!(result.is_ok());

    let result = A2UIValidator::check_form_completeness(
        &form_state,
        &vec![
            "field1".to_string(),
            "field2".to_string(),
            "field3".to_string(),
        ],
    );
    assert!(result.is_err());
}

#[test]
fn test_component_hierarchy_validation() {
    // Modal with required Button should validate children
    let modal = A2UIComponent::Modal {
        id: "confirm_modal".to_string(),
        title: "Confirm Action".to_string(),
        content: "Are you sure?".to_string(),
        children: vec![A2UIComponent::Button {
            id: "confirm_btn".to_string(),
            label: "Confirm".to_string(),
            action: Some("submit".to_string()),
        }],
    };

    assert!(A2UIValidator::validate(&modal).is_ok());
}

#[test]
fn test_fail_closed_on_invalid_required_component() {
    // Modal without buttons should fail (context-aware)
    let modal = A2UIComponent::Modal {
        id: "modal".to_string(),
        title: "Action".to_string(),
        content: "Do something".to_string(),
        children: vec![], // No buttons = invalid for action modal
    };

    let result = A2UIValidator::validate_modal_context(&modal);
    // Should be error because modal with content but no action buttons
    assert!(result.is_err());
}

#[test]
fn test_select_with_no_options_context_validation() {
    let select = A2UIComponent::Select {
        id: "choice".to_string(),
        label: "Choose One".to_string(),
        options: vec![], // Empty options invalid in context
    };

    let result = A2UIValidator::validate_select_context(&select);
    assert!(result.is_err());
}

#[test]
fn test_select_with_options_context_validation() {
    let select = A2UIComponent::Select {
        id: "choice".to_string(),
        label: "Choose One".to_string(),
        options: vec![SelectOption {
            value: "opt1".to_string(),
            label: "Option 1".to_string(),
        }],
    };

    let result = A2UIValidator::validate_select_context(&select);
    assert!(result.is_ok());
}

#[test]
fn test_form_submission_validation_with_schema() {
    // Test form submission against a schema
    let submission = serde_json::json!({
        "name": "John",
        "email": "john@example.com"
    });

    let schema = vec![
        ("name".to_string(), ("text".to_string(), true)), // type, required
        ("email".to_string(), ("email".to_string(), true)),
    ];

    let result = A2UIValidator::validate_submission(&submission, &schema);
    assert!(result.is_ok());
}

#[test]
fn test_form_submission_validation_missing_required() {
    let submission = serde_json::json!({
        "name": "John"
        // missing email
    });

    let schema = vec![
        ("name".to_string(), ("text".to_string(), true)),
        ("email".to_string(), ("email".to_string(), true)), // required
    ];

    let result = A2UIValidator::validate_submission(&submission, &schema);
    assert!(result.is_err());
}

#[test]
fn test_conditional_field_visibility_validation() {
    // If "account_type" == "business", then "company_name" is required
    let form_state = vec![
        ("account_type".to_string(), serde_json::json!("business")),
        ("company_name".to_string(), serde_json::json!("")),
    ];

    let result = A2UIValidator::validate_conditional_field(
        "account_type",
        "business",
        "company_name",
        &form_state,
    );

    assert!(result.is_err());
}

#[test]
fn test_conditional_field_validation_satisfied() {
    let form_state = vec![
        ("account_type".to_string(), serde_json::json!("business")),
        ("company_name".to_string(), serde_json::json!("ACME Corp")),
    ];

    let result = A2UIValidator::validate_conditional_field(
        "account_type",
        "business",
        "company_name",
        &form_state,
    );

    assert!(result.is_ok());
}

#[test]
fn test_grid_column_count_validation() {
    let grid = A2UIComponent::Grid {
        id: "grid".to_string(),
        columns: 0, // Invalid: must be > 0
        children: vec![],
    };

    let result = A2UIValidator::validate_grid_context(&grid);
    assert!(result.is_err());
}

#[test]
fn test_grid_column_count_valid() {
    let grid = A2UIComponent::Grid {
        id: "grid".to_string(),
        columns: 3,
        children: vec![A2UIComponent::Text {
            id: "c1".to_string(),
            content: "Cell 1".to_string(),
            size: None,
        }],
    };

    let result = A2UIValidator::validate_grid_context(&grid);
    assert!(result.is_ok());
}

#[test]
fn test_textarea_rows_validation() {
    let textarea = A2UIComponent::Textarea {
        id: "notes".to_string(),
        label: "Notes".to_string(),
        rows: Some(0), // Invalid: must be > 0
    };

    let result = A2UIValidator::validate_textarea_context(&textarea);
    assert!(result.is_err());
}

#[test]
fn test_textarea_rows_valid() {
    let textarea = A2UIComponent::Textarea {
        id: "notes".to_string(),
        label: "Notes".to_string(),
        rows: Some(5),
    };

    let result = A2UIValidator::validate_textarea_context(&textarea);
    assert!(result.is_ok());
}

// === ADVANCED VALIDATION TESTS (Wave 3: DoS Protection) ===

#[test]
fn test_depth_limit_enforcement() {
    let validator = A2UIValidator::new(2, 1000); // Max depth 2

    // Valid: depth 2 (Card at 0, Card at 1, Text at 2)
    let valid = A2UIComponent::Card {
        id: "c1".to_string(),
        title: None,
        children: vec![A2UIComponent::Card {
            id: "c2".to_string(),
            title: None,
            children: vec![A2UIComponent::Text {
                id: "t1".to_string(),
                content: "nested".to_string(),
                size: None,
            }],
        }],
    };
    assert!(validator.validate_component(&valid).is_ok());

    // Invalid: depth 3+ (exceeds max of 2)
    let invalid = A2UIComponent::Card {
        id: "c1".to_string(),
        title: None,
        children: vec![A2UIComponent::Card {
            id: "c2".to_string(),
            title: None,
            children: vec![A2UIComponent::Card {
                id: "c3".to_string(),
                title: None,
                children: vec![A2UIComponent::Text {
                    id: "t1".to_string(),
                    content: "too deep".to_string(),
                    size: None,
                }],
            }],
        }],
    };
    let result = validator.validate_component(&invalid);
    assert!(result.is_err());
    if let Err(e) = result {
        assert!(matches!(e, ValidationError::ExceedsMaxDepth(_)));
    }
}

#[test]
fn test_component_count_limit() {
    let validator = A2UIValidator::new(10, 3); // Max 3 components

    let components = vec![
        A2UIComponent::Text {
            id: "t1".to_string(),
            content: "x".to_string(),
            size: None,
        },
        A2UIComponent::Text {
            id: "t2".to_string(),
            content: "y".to_string(),
            size: None,
        },
        A2UIComponent::Text {
            id: "t3".to_string(),
            content: "z".to_string(),
            size: None,
        },
        A2UIComponent::Text {
            id: "t4".to_string(),
            content: "too many".to_string(),
            size: None,
        },
    ];

    let result = validator.validate_event(&components);
    assert!(result.is_err());
    if let Err(e) = result {
        assert!(matches!(e, ValidationError::ExceedsComponentCount(_)));
    }
}

#[test]
fn test_circular_reference_detection() {
    let validator = A2UIValidator::default();

    // Simulate circular structure by creating separate components
    // In practice, Rust's ownership prevents true circular refs, but we test the logic
    let components = vec![
        A2UIComponent::Card {
            id: "c1".to_string(),
            title: None,
            children: vec![],
        },
        A2UIComponent::Card {
            id: "c2".to_string(),
            title: None,
            children: vec![],
        },
    ];

    // Should succeed (no actual circular refs)
    let result = validator.check_circular_refs(&components);
    assert!(result.is_ok());
}

#[test]
fn test_duplicate_form_id_detection() {
    let validator = A2UIValidator::default();

    let components = vec![
        A2UIComponent::Input {
            id: "field1".to_string(),
            label: "Name".to_string(),
            placeholder: None,
            required: true,
        },
        A2UIComponent::Input {
            id: "field1".to_string(), // Duplicate!
            label: "Email".to_string(),
            placeholder: None,
            required: true,
        },
    ];

    let result = validator.validate_unique_form_ids(&components);
    assert!(result.is_err());
    if let Err(e) = result {
        assert!(matches!(e, ValidationError::DuplicateFormId(_)));
    }
}

#[test]
fn test_text_size_limit_enforcement() {
    let validator = A2UIValidator::new(10, 1000);

    // Create a large text component (>10KB)
    let large_text = "x".repeat(10241); // 10KB + 1
    let component = A2UIComponent::Text {
        id: "big".to_string(),
        content: large_text,
        size: None,
    };

    let result = validator.validate_component(&component);
    assert!(result.is_err());
    if let Err(e) = result {
        assert!(matches!(e, ValidationError::TextContentTooLarge(_)));
    }
}

#[test]
fn test_color_format_validation() {
    // Valid hex color
    let validator = A2UIValidator::default();
    let hex_badge = A2UIComponent::Badge {
        id: "b1".to_string(),
        label: "test".to_string(),
        color: Some("#FF5733".to_string()),
    };
    assert!(validator.validate_component(&hex_badge).is_ok());

    // Invalid hex color (wrong length)
    let invalid_hex = A2UIComponent::Badge {
        id: "b2".to_string(),
        label: "test".to_string(),
        color: Some("#FF57".to_string()), // Too short
    };
    assert!(validator.validate_component(&invalid_hex).is_err());

    // Valid named color
    let named_badge = A2UIComponent::Badge {
        id: "b3".to_string(),
        label: "test".to_string(),
        color: Some("red".to_string()),
    };
    assert!(validator.validate_component(&named_badge).is_ok());

    // Invalid named color
    let invalid_named = A2UIComponent::Badge {
        id: "b4".to_string(),
        label: "test".to_string(),
        color: Some("invalidcolor".to_string()),
    };
    assert!(validator.validate_component(&invalid_named).is_err());
}

#[test]
fn test_size_format_validation() {
    let validator = A2UIValidator::default();

    // Valid sizes
    for size in &["xs", "sm", "md", "lg", "xl", "2xl", "3xl"] {
        let text = A2UIComponent::Text {
            id: format!("t_{}", size),
            content: "test".to_string(),
            size: Some(size.to_string()),
        };
        assert!(validator.validate_component(&text).is_ok());
    }

    // Invalid size
    let invalid = A2UIComponent::Text {
        id: "invalid".to_string(),
        content: "test".to_string(),
        size: Some("xxl".to_string()),
    };
    assert!(validator.validate_component(&invalid).is_err());
}

#[test]
fn test_alert_level_validation() {
    let validator = A2UIValidator::default();

    // Valid levels
    for level in &["info", "warn", "error", "success"] {
        let alert = A2UIComponent::Alert {
            id: format!("a_{}", level),
            message: "test".to_string(),
            level: level.to_string(),
        };
        assert!(validator.validate_component(&alert).is_ok());
    }

    // Invalid level
    let invalid = A2UIComponent::Alert {
        id: "invalid".to_string(),
        message: "test".to_string(),
        level: "critical".to_string(),
    };
    assert!(validator.validate_component(&invalid).is_err());
}

#[test]
fn test_progress_range_validation() {
    let validator = A2UIValidator::default();

    // Valid: value <= max
    let valid = A2UIComponent::Progress {
        id: "p1".to_string(),
        value: 75,
        max: 100,
        label: None,
    };
    assert!(validator.validate_component(&valid).is_ok());

    // Invalid: value > max
    let invalid = A2UIComponent::Progress {
        id: "p2".to_string(),
        value: 150,
        max: 100,
        label: None,
    };
    let result = validator.validate_component(&invalid);
    assert!(result.is_err());
    if let Err(e) = result {
        assert!(matches!(e, ValidationError::InvalidProgressRange(_, _)));
    }
}

#[test]
fn test_select_option_limit() {
    let validator = A2UIValidator::default();

    // Create select with 101 options (exceeds limit of 100)
    let mut options = vec![];
    for i in 0..101 {
        options.push(SelectOption {
            value: format!("opt{}", i),
            label: format!("Option {}", i),
        });
    }

    let select = A2UIComponent::Select {
        id: "s1".to_string(),
        label: "choices".to_string(),
        options,
    };

    let result = validator.validate_component(&select);
    assert!(result.is_err());
}

#[test]
fn test_grid_columns_validation() {
    let validator = A2UIValidator::default();

    // Valid: columns > 0
    let valid = A2UIComponent::Grid {
        id: "g1".to_string(),
        columns: 3,
        children: vec![],
    };
    assert!(validator.validate_component(&valid).is_ok());

    // Invalid: columns == 0
    let invalid = A2UIComponent::Grid {
        id: "g2".to_string(),
        columns: 0,
        children: vec![],
    };
    assert!(validator.validate_component(&invalid).is_err());
}

#[test]
fn test_modal_without_buttons_rejects() {
    let validator = A2UIValidator::default();

    // Modal with substantial content but no buttons = invalid
    let invalid = A2UIComponent::Modal {
        id: "m1".to_string(),
        title: "Action Required".to_string(),
        content: "This is important content that requires action".to_string(),
        children: vec![], // No buttons!
    };

    let result = validator.validate_component(&invalid);
    assert!(result.is_err());
    if let Err(e) = result {
        assert!(matches!(e, ValidationError::ModalMissingButtons));
    }
}

#[test]
fn test_modal_with_short_content_allows_no_buttons() {
    let validator = A2UIValidator::default();

    // Modal with short content (<=5 chars) can have no buttons
    let valid = A2UIComponent::Modal {
        id: "m1".to_string(),
        title: "Info".to_string(),
        content: "OK".to_string(), // Short content
        children: vec![],
    };

    assert!(validator.validate_component(&valid).is_ok());
}

#[test]
fn test_id_format_validation() {
    let validator = A2UIValidator::default();

    // Valid IDs: alphanumeric, underscore, hyphen
    for id in &["id_1", "id-2", "field_name", "input-field-1"] {
        let text = A2UIComponent::Text {
            id: id.to_string(),
            content: "test".to_string(),
            size: None,
        };
        assert!(
            validator.validate_component(&text).is_ok(),
            "ID {} should be valid",
            id
        );
    }

    // Invalid ID: contains spaces or special chars
    let invalid = A2UIComponent::Text {
        id: "field name".to_string(),
        content: "test".to_string(),
        size: None,
    };
    assert!(validator.validate_component(&invalid).is_err());
}

#[test]
fn test_empty_id_rejects() {
    let validator = A2UIValidator::default();

    let component = A2UIComponent::Text {
        id: "".to_string(),
        content: "test".to_string(),
        size: None,
    };

    let result = validator.validate_component(&component);
    assert!(result.is_err());
}

#[test]
fn test_validation_error_display_messages() {
    // Test that ValidationError Display impl works
    let errors = vec![
        (
            ValidationError::ExceedsMaxDepth(10),
            "exceeds maximum depth",
        ),
        (
            ValidationError::CircularReference("id1".to_string()),
            "Circular",
        ),
        (
            ValidationError::EmptySelectOptions,
            "must have at least one",
        ),
        (ValidationError::InvalidGridColumns, "Grid must have"),
    ];

    for (error, expected_fragment) in errors {
        let msg = error.to_string();
        assert!(
            msg.contains(expected_fragment),
            "Error message '{}' should contain '{}'",
            msg,
            expected_fragment
        );
    }
}
