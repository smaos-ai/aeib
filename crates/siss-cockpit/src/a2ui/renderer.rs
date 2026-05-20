use siss_agent_shell::a2ui::A2UIComponent;

/// Cockpit Renderer: Converts A2UIComponent JSON → safe HTML snippets
pub struct Renderer;

impl Renderer {
    /// Render a single A2UIComponent to HTML string
    /// Implements XSS protection via HTML escaping
    pub fn render(component: &A2UIComponent) -> String {
        match component {
            // === DISPLAY (8 types) ===
            A2UIComponent::Text { content, size } => {
                let size_class = if size.is_empty() { "md" } else { size };
                let escaped = escape_html(content);
                format!(r#"<div class="a2ui-text text-{}"><p>{}</p></div>"#, size_class, escaped)
            }

            A2UIComponent::Badge { label, color } => {
                let color_class = if color.is_empty() { "default" } else { color };
                let escaped = escape_html(label);
                format!(r#"<span class="a2ui-badge badge-{}">{}</span>"#, color_class, escaped)
            }

            A2UIComponent::Alert { message, level } => {
                let level_class = if level.is_empty() { "info" } else { level };
                let escaped = escape_html(message);
                format!(r#"<div class="a2ui-alert alert-{}" role="alert"><strong>{}</strong></div>"#, level_class, escaped)
            }

            A2UIComponent::Progress { value, max, label } => {
                let percentage = (*value as f32 / *max as f32 * 100.0).min(100.0).max(0.0) as u32;
                let label_html = match label {
                    Some(lbl) => format!(r#" <span class="progress-label">{}</span>"#, escape_html(lbl)),
                    None => String::new(),
                };
                format!(
                    r#"<div class="a2ui-progress"><div class="progress-bar" style="width: {}%;" role="progressbar" aria-valuenow="{}" aria-valuemin="0" aria-valuemax="100"></div>{}</div>"#,
                    percentage, value, label_html
                )
            }

            A2UIComponent::Divider => {
                r#"<hr class="a2ui-divider" />"#.to_string()
            }

            A2UIComponent::Link { text, href } => {
                let text_escaped = escape_html(text);
                let href_escaped = escape_html(href);
                format!(r#"<a href="{}" class="a2ui-link">{}</a>"#, href_escaped, text_escaped)
            }

            A2UIComponent::Tooltip { text, content } => {
                let text_escaped = escape_html(text);
                let content_escaped = escape_html(content);
                format!(
                    r#"<span class="a2ui-tooltip" title="{}">{}</span>"#,
                    content_escaped, text_escaped
                )
            }

            A2UIComponent::Breadcrumb { items } => {
                let breadcrumbs = items
                    .iter()
                    .enumerate()
                    .map(|(i, item)| {
                        let escaped = escape_html(item);
                        if i == items.len() - 1 {
                            format!(r#"<span class="breadcrumb-item active" aria-current="page">{}</span>"#, escaped)
                        } else {
                            format!("<span class=\"breadcrumb-item\"><a href=\"#\">{}</a></span>", escaped)
                        }
                    })
                    .collect::<Vec<_>>()
                    .join(r#"<span class="breadcrumb-separator">/</span>"#);
                format!(r#"<nav class="a2ui-breadcrumb" aria-label="breadcrumb">{}</nav>"#, breadcrumbs)
            }

            // === INTERACTIVE FORMS (6 types) ===
            A2UIComponent::Input { id, label, placeholder, required } => {
                let required_attr = if *required { " required" } else { "" };
                let placeholder_attr = if placeholder.is_empty() {
                    String::new()
                } else {
                    format!(r#" placeholder="{}""#, escape_html(placeholder))
                };
                format!(
                    r#"<div class="a2ui-input-wrapper"><label for="{}">{}</label><input type="text" id="{}" name="{}"{}{} class="a2ui-input" /></div>"#,
                    escape_html(id), escape_html(label), escape_html(id), escape_html(id), placeholder_attr, required_attr
                )
            }

            A2UIComponent::Textarea { id, label, rows } => {
                format!(
                    r#"<div class="a2ui-textarea-wrapper"><label for="{}">{}</label><textarea id="{}" name="{}" rows="{}" class="a2ui-textarea"></textarea></div>"#,
                    escape_html(id), escape_html(label), escape_html(id), escape_html(id), rows
                )
            }

            A2UIComponent::Select { id, label, options } => {
                let option_html = options
                    .iter()
                    .map(|opt| {
                        format!(
                            r#"<option value="{}">{}</option>"#,
                            escape_html(&opt.value),
                            escape_html(&opt.label)
                        )
                    })
                    .collect::<Vec<_>>()
                    .join("");
                format!(
                    r#"<div class="a2ui-select-wrapper"><label for="{}">{}</label><select id="{}" name="{}" class="a2ui-select">{}</select></div>"#,
                    escape_html(id), escape_html(label), escape_html(id), escape_html(id), option_html
                )
            }

            A2UIComponent::Checkbox { id, label } => {
                format!(
                    r#"<div class="a2ui-checkbox-wrapper"><input type="checkbox" id="{}" name="{}" class="a2ui-checkbox" /><label for="{}">{}</label></div>"#,
                    escape_html(id), escape_html(id), escape_html(id), escape_html(label)
                )
            }

            A2UIComponent::Radio { id, label, options } => {
                let radio_html = options
                    .iter()
                    .enumerate()
                    .map(|(i, opt)| {
                        let radio_id = format!("{}_{}", id, i);
                        format!(
                            r#"<div class="a2ui-radio-item"><input type="radio" id="{}" name="{}" value="{}" class="a2ui-radio" /><label for="{}">{}</label></div>"#,
                            escape_html(&radio_id), escape_html(id), escape_html(&opt.value), escape_html(&radio_id), escape_html(&opt.label)
                        )
                    })
                    .collect::<Vec<_>>()
                    .join("");
                format!(
                    r#"<fieldset class="a2ui-radio-wrapper"><legend>{}</legend>{}</fieldset>"#,
                    escape_html(label), radio_html
                )
            }

            A2UIComponent::Button { id, label, action } => {
                let button_type = if action == "submit" { "submit" } else { "button" };
                format!(
                    r#"<button id="{}" class="a2ui-button" type="{}">{}</button>"#,
                    escape_html(id), button_type, escape_html(label)
                )
            }

            // === LAYOUT (4 types) ===
            A2UIComponent::Card { title, children } => {
                let children_html = children
                    .iter()
                    .map(|child| Self::render(child))
                    .collect::<Vec<_>>()
                    .join("");
                format!(
                    r#"<div class="a2ui-card"><div class="card-header"><h3 class="card-title">{}</h3></div><div class="card-body">{}</div></div>"#,
                    escape_html(title), children_html
                )
            }

            A2UIComponent::Grid { columns, children } => {
                let children_html = children
                    .iter()
                    .map(|child| format!(r#"<div class="grid-item">{}</div>"#, Self::render(child)))
                    .collect::<Vec<_>>()
                    .join("");
                format!(
                    r#"<div class="a2ui-grid" style="grid-template-columns: repeat({}, 1fr);">{}</div>"#,
                    columns, children_html
                )
            }

            A2UIComponent::Modal { id, title, children } => {
                let children_html = children
                    .iter()
                    .map(|child| Self::render(child))
                    .collect::<Vec<_>>()
                    .join("");
                format!(
                    r#"<div id="{}" class="a2ui-modal" role="dialog" aria-labelledby="modal-title-{}"><div class="modal-content"><div class="modal-header"><h2 id="modal-title-{}" class="modal-title">{}</h2></div><div class="modal-body">{}</div></div></div>"#,
                    escape_html(id), escape_html(id), escape_html(id), escape_html(title), children_html
                )
            }

            A2UIComponent::Table { headers, rows } => {
                let header_html = headers
                    .iter()
                    .map(|h| format!(r#"<th>{}</th>"#, escape_html(h)))
                    .collect::<Vec<_>>()
                    .join("");
                let row_html = rows
                    .iter()
                    .map(|row| {
                        let cells = row
                            .iter()
                            .map(|cell| format!(r#"<td>{}</td>"#, escape_html(cell)))
                            .collect::<Vec<_>>()
                            .join("");
                        format!(r#"<tr>{}</tr>"#, cells)
                    })
                    .collect::<Vec<_>>()
                    .join("");
                format!(
                    r#"<table class="a2ui-table"><thead><tr>{}</tr></thead><tbody>{}</tbody></table>"#,
                    header_html, row_html
                )
            }
        }
    }
}

/// Escape HTML special characters to prevent XSS
fn escape_html(s: &str) -> String {
    s.chars()
        .map(|c| match c {
            '&' => "&amp;".to_string(),
            '<' => "&lt;".to_string(),
            '>' => "&gt;".to_string(),
            '"' => "&quot;".to_string(),
            '\'' => "&#39;".to_string(),
            _ => c.to_string(),
        })
        .collect()
}

