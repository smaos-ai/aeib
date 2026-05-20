use crate::a2ui::schema::A2UIComponent;

pub struct A2UIValidator;

impl A2UIValidator {
    /// Validate A2UIComponent against 18-primitive schema (fail-closed)
    pub fn validate(component: &A2UIComponent) -> Result<(), String> {
        match component {
            // Display components
            A2UIComponent::Text { id, content, .. } => {
                Self::validate_id(id)?;
                if content.is_empty() {
                    return Err("Text content must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Badge { id, label, .. } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Badge label must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Alert { id, message, .. } => {
                Self::validate_id(id)?;
                if message.is_empty() {
                    return Err("Alert message must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Progress { id, value, max, .. } => {
                Self::validate_id(id)?;
                if value > max {
                    return Err("Progress value cannot exceed max".to_string());
                }
                Ok(())
            }
            A2UIComponent::Divider { id } => {
                Self::validate_id(id)?;
                Ok(())
            }
            A2UIComponent::Link { id, label, href } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Link label must not be empty".to_string());
                }
                if href.is_empty() {
                    return Err("Link href must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Tooltip { id, text, content } => {
                Self::validate_id(id)?;
                if text.is_empty() {
                    return Err("Tooltip text must not be empty".to_string());
                }
                if content.is_empty() {
                    return Err("Tooltip content must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Breadcrumb { id, .. } => {
                Self::validate_id(id)?;
                Ok(())
            }
            // Form components
            A2UIComponent::Input { id, label, .. } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Input label must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Textarea { id, label, .. } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Textarea label must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Select { id, label, .. } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Select label must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Checkbox { id, label, .. } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Checkbox label must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Radio { id, label, value, .. } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Radio label must not be empty".to_string());
                }
                if value.is_empty() {
                    return Err("Radio value must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Button { id, label, .. } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Button label must not be empty".to_string());
                }
                Ok(())
            }
            // Layout components
            A2UIComponent::Card { id, children, .. } => {
                Self::validate_id(id)?;
                for child in children {
                    Self::validate(child)?;
                }
                Ok(())
            }
            A2UIComponent::Grid { id, children, .. } => {
                Self::validate_id(id)?;
                for child in children {
                    Self::validate(child)?;
                }
                Ok(())
            }
            A2UIComponent::Modal { id, title, content, children } => {
                Self::validate_id(id)?;
                if title.is_empty() {
                    return Err("Modal title must not be empty".to_string());
                }
                if content.is_empty() {
                    return Err("Modal content must not be empty".to_string());
                }
                for child in children {
                    Self::validate(child)?;
                }
                Ok(())
            }
            A2UIComponent::Table { id, .. } => {
                Self::validate_id(id)?;
                Ok(())
            }
        }
    }

    fn validate_id(id: &str) -> Result<(), String> {
        if id.is_empty() {
            Err("Component ID must not be empty".to_string())
        } else {
            Ok(())
        }
    }
}
