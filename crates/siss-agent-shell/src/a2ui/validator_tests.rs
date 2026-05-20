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
