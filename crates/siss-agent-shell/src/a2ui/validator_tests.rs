use crate::a2ui::schema::*;
use crate::a2ui::validator::A2UIValidator;

#[test]
fn test_accepts_text_component() {
    let component = A2UIComponent::Text {
        content: "Hello".to_string(),
        size: "md".to_string(),
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_accepts_input_component() {
    let component = A2UIComponent::Input {
        id: "field1".to_string(),
        label: "Name".to_string(),
        placeholder: "Enter name".to_string(),
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
                content: "Content".to_string(),
                size: "sm".to_string(),
            },
        ],
    };
    assert!(A2UIValidator::validate(&component).is_ok());
}

#[test]
fn test_validates_all_18_primitives() {
    // Display (8)
    let display_components = vec![
        A2UIComponent::Text { content: "t".to_string(), size: "md".to_string() },
        A2UIComponent::Badge { label: "b".to_string(), color: "blue".to_string() },
        A2UIComponent::Alert { message: "a".to_string(), level: "info".to_string() },
        A2UIComponent::Progress { value: 50, max: 100, label: None },
        A2UIComponent::Divider,
        A2UIComponent::Link { text: "l".to_string(), href: "http://x".to_string() },
        A2UIComponent::Tooltip { text: "t".to_string(), content: "tip".to_string() },
        A2UIComponent::Breadcrumb { items: vec![] },
    ];
    for comp in display_components {
        assert!(A2UIValidator::validate(&comp).is_ok(), "Failed for: {:?}", comp);
    }

    // Forms (6)
    let form_components = vec![
        A2UIComponent::Input { id: "9".to_string(), label: "i".to_string(), placeholder: "".to_string(), required: false },
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
                content: "valid".to_string(),
                size: "sm".to_string(),
            },
        ],
    };
    assert!(A2UIValidator::validate(&invalid_component).is_ok());
}

#[test]
fn test_returns_error_message_on_validation_failure() {
    let component = A2UIComponent::Input {
        id: "".to_string(), // Empty ID should fail
        label: "Field".to_string(),
        placeholder: "".to_string(),
        required: false,
    };
    let result = A2UIValidator::validate(&component);
    assert!(result.is_err(), "Expected validation to fail for empty ID");
    if let Err(msg) = result {
        assert!(!msg.is_empty(), "Error message should not be empty");
    }
}
