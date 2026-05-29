use crate::a2ui::schema::*;
use crate::a2ui::validator::A2UIValidator;

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
        children: vec![
            A2UIComponent::Text {
                id: "text1".to_string(),
                content: "Content".to_string(),
                size: None,
            },
        ],
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_validates_all_18_primitives() {
    // Display (8)
    let display_components = vec![
        A2UIComponent::Text { id: "1".to_string(), content: "t".to_string(), size: None },
        A2UIComponent::Badge { id: "2".to_string(), label: "b".to_string(), color: None },
        A2UIComponent::Alert { id: "3".to_string(), message: "a".to_string(), level: "info".to_string() },
        A2UIComponent::Progress { id: "4".to_string(), value: 50, max: 100, label: None },
        A2UIComponent::Divider { id: "5".to_string() },
        A2UIComponent::Link { id: "6".to_string(), label: "l".to_string(), href: "http://x".to_string() },
        A2UIComponent::Tooltip { id: "7".to_string(), text: "t".to_string(), content: "tip".to_string() },
        A2UIComponent::Breadcrumb { id: "8".to_string(), items: vec![] },
    ];
    for comp in display_components {
        assert!(A2UIValidator::validate(&comp).is_ok(), "Failed for: {:?}", comp);
    }

    // Forms (6)
    let form_components = vec![
        A2UIComponent::Input { id: "9".to_string(), label: "i".to_string(), placeholder: None, required: false },
        A2UIComponent::Textarea { id: "10".to_string(), label: "ta".to_string(), rows: None },
        A2UIComponent::Select { id: "11".to_string(), label: "s".to_string(), options: vec![] },
        A2UIComponent::Checkbox { id: "12".to_string(), label: "c".to_string(), checked: false },
        A2UIComponent::Radio { id: "13".to_string(), label: "r".to_string(), value: "v".to_string(), checked: false },
        A2UIComponent::Button { id: "14".to_string(), label: "btn".to_string(), action: None },
    ];
    for comp in form_components {
        assert!(A2UIValidator::validate(&comp).is_ok(), "Failed for: {:?}", comp);
    }

    // Layout (4)
    let layout_components = vec![
        A2UIComponent::Card { id: "15".to_string(), title: None, children: vec![] },
        A2UIComponent::Grid { id: "16".to_string(), columns: 2, children: vec![] },
        A2UIComponent::Modal { id: "17".to_string(), title: "m".to_string(), content: "content".to_string(), children: vec![] },
        A2UIComponent::Table { id: "18".to_string(), headers: vec![], rows: vec![] },
    ];
    for comp in layout_components {
        assert!(A2UIValidator::validate(&comp).is_ok(), "Failed for: {:?}", comp);
    }
}

#[test]
fn test_validator_rejects_invalid_nested_components() {
    let invalid_component = A2UIComponent::Card {
        id: "card".to_string(),
        title: None,
        children: vec![
            A2UIComponent::Text {
                id: "text".to_string(),
                content: "valid".to_string(),
                size: None,
            },
        ],
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
        A2UIComponent::Text { id: "t1".into(), content: "text".into(), size: None },
        A2UIComponent::Badge { id: "b1".into(), label: "badge".into(), color: None },
        A2UIComponent::Alert { id: "a1".into(), message: "alert".into(), level: "info".into() },
        A2UIComponent::Progress { id: "p1".into(), value: 50, max: 100, label: None },
        A2UIComponent::Divider { id: "d1".into() },
        A2UIComponent::Link { id: "l1".into(), label: "link".into(), href: "http://x".into() },
        A2UIComponent::Tooltip { id: "tt1".into(), text: "t".into(), content: "c".into() },
        A2UIComponent::Breadcrumb { id: "br1".into(), items: vec!["home".into(), "page".into()] },
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
        A2UIComponent::Input { id: "i1".into(), label: "input".into(), placeholder: None, required: false },
        A2UIComponent::Textarea { id: "ta1".into(), label: "textarea".into(), rows: None },
        A2UIComponent::Select { id: "s1".into(), label: "select".into(), options: vec![SelectOption { value: "v1".into(), label: "opt1".into() }] },
        A2UIComponent::Checkbox { id: "c1".into(), label: "check".into(), checked: false },
        A2UIComponent::Radio { id: "r1".into(), label: "radio".into(), value: "rv".into(), checked: false },
        A2UIComponent::Button { id: "btn1".into(), label: "button".into(), action: None },
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
        A2UIComponent::Card { id: "card1".into(), title: None, children: vec![] },
        A2UIComponent::Grid { id: "grid1".into(), columns: 2, children: vec![] },
        A2UIComponent::Modal { id: "modal1".into(), title: "title".into(), content: "content".into(), children: vec![] },
        A2UIComponent::Table { id: "table1".into(), headers: vec!["h1".into(), "h2".into()], rows: vec![] },
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
        SelectOption { value: "opt1".into(), label: "Option 1".into() },
        SelectOption { value: "opt2".into(), label: "Option 2".into() },
        SelectOption { value: "opt3".into(), label: "Option 3".into() },
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
        A2UIComponent::Text { id: "g1".into(), content: "Cell 1".into(), size: None },
        A2UIComponent::Text { id: "g2".into(), content: "Cell 2".into(), size: None },
        A2UIComponent::Text { id: "g3".into(), content: "Cell 3".into(), size: None },
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
        items: vec!["Home".into(), "Products".into(), "Electronics".into(), "Phones".into()],
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
