use siss_agent_shell::a2ui::schema::A2UIComponent;

pub struct ReactRendererSpec;

impl ReactRendererSpec {
    pub fn render_jsx(component: &A2UIComponent) -> String {
        match component {
            A2UIComponent::Button { id, label, action: _ } => {
                format!(
                    r#"<button id="{}" onClick={{() => {{}}}}>
  {}
</button>"#,
                    Self::escape_html(id),
                    Self::escape_html(label)
                )
            }
            A2UIComponent::Input {
                id,
                label,
                placeholder,
                required,
            } => {
                let placeholder_attr = placeholder
                    .as_ref()
                    .map(|p| format!(r#" placeholder="{}""#, Self::escape_html(p)))
                    .unwrap_or_default();
                let required_attr = if *required { " required" } else { "" };
                format!(
                    r#"<div>
  <label htmlFor="{}">{}</label>
  <input id="{}" type="text"{}{} />
</div>"#,
                    Self::escape_html(id),
                    Self::escape_html(label),
                    Self::escape_html(id),
                    placeholder_attr,
                    required_attr
                )
            }
            A2UIComponent::Select { id, label, options } => {
                let options_jsx = options
                    .iter()
                    .map(|opt| {
                        format!(
                            r#"<option key="{}" value="{}">{}</option>"#,
                            Self::escape_html(&opt.value),
                            Self::escape_html(&opt.value),
                            Self::escape_html(&opt.label)
                        )
                    })
                    .collect::<Vec<_>>()
                    .join("\n  ");
                format!(
                    r#"<div>
  <label htmlFor="{}">{}</label>
  <select id="{}">
    {}
  </select>
</div>"#,
                    Self::escape_html(id),
                    Self::escape_html(label),
                    Self::escape_html(id),
                    options_jsx
                )
            }
            A2UIComponent::Table { id, headers, rows } => {
                let header_jsx = headers
                    .iter()
                    .map(|h| format!(r#"<th>{}</th>"#, Self::escape_html(h)))
                    .collect::<Vec<_>>()
                    .join("");
                let rows_jsx = rows
                    .iter()
                    .map(|row| {
                        let cells = row
                            .iter()
                            .map(|cell| format!(r#"<td>{}</td>"#, Self::escape_html(cell)))
                            .collect::<Vec<_>>()
                            .join("");
                        format!(r#"<tr>{}</tr>"#, cells)
                    })
                    .collect::<Vec<_>>()
                    .join("\n  ");
                format!(
                    r#"<table id="{}">
  <thead>
    <tr>{}</tr>
  </thead>
  <tbody>
    {}
  </tbody>
</table>"#,
                    Self::escape_html(id),
                    header_jsx,
                    rows_jsx
                )
            }
            A2UIComponent::Modal {
                id,
                title,
                content,
                children,
            } => {
                let children_jsx = children
                    .iter()
                    .map(|child| Self::render_jsx(child))
                    .collect::<Vec<_>>()
                    .join("\n  ");
                format!(
                    r#"<div id="{}" role="dialog">
  <h2>{}</h2>
  <p>{}</p>
  {}
</div>"#,
                    Self::escape_html(id),
                    Self::escape_html(title),
                    Self::escape_html(content),
                    children_jsx
                )
            }
            A2UIComponent::Text { id, content, size } => {
                let class_attr = size
                    .as_ref()
                    .map(|s| format!(r#" className="text-{}""#, Self::escape_html(s)))
                    .unwrap_or_default();
                format!(
                    r#"<div id="{}"{}>
  {}
</div>"#,
                    Self::escape_html(id),
                    class_attr,
                    Self::escape_html(content)
                )
            }
            A2UIComponent::Badge { id, label, color } => {
                let class_attr = color
                    .as_ref()
                    .map(|c| format!(r#" className="badge-{}""#, Self::escape_html(c)))
                    .unwrap_or_default();
                format!(
                    r#"<span id="{}"{}>
  {}
</span>"#,
                    Self::escape_html(id),
                    class_attr,
                    Self::escape_html(label)
                )
            }
            A2UIComponent::Alert {
                id,
                message,
                level,
            } => {
                format!(
                    r#"<div id="{}" role="alert" className="alert-{}">
  {}
</div>"#,
                    Self::escape_html(id),
                    Self::escape_html(level),
                    Self::escape_html(message)
                )
            }
            A2UIComponent::Progress { id, value, max, label } => {
                let label_jsx = label
                    .as_ref()
                    .map(|l| format!(r#"<p>{}</p>"#, Self::escape_html(l)))
                    .unwrap_or_default();
                format!(
                    r#"<div id="{}">
  {}
  <progress value="{}" max="{}" aria-valuenow="{}" aria-valuemax="{}"></progress>
</div>"#,
                    Self::escape_html(id),
                    label_jsx,
                    value,
                    max,
                    value,
                    max
                )
            }
            A2UIComponent::Divider { id } => {
                format!(r#"<hr id="{}" />"#, Self::escape_html(id))
            }
            A2UIComponent::Link { id, label, href } => {
                format!(
                    r#"<a id="{}" href="{}">{}</a>"#,
                    Self::escape_html(id),
                    Self::escape_html(href),
                    Self::escape_html(label)
                )
            }
            A2UIComponent::Tooltip { id, text, content } => {
                format!(
                    r#"<div id="{}" title="{}" role="tooltip">
  {}
</div>"#,
                    Self::escape_html(id),
                    Self::escape_html(text),
                    Self::escape_html(content)
                )
            }
            A2UIComponent::Breadcrumb { id, items } => {
                let items_jsx = items
                    .iter()
                    .map(|item| format!(r#"<li>{}</li>"#, Self::escape_html(item)))
                    .collect::<Vec<_>>()
                    .join("");
                format!(
                    r#"<nav id="{}" aria-label="breadcrumb">
  <ol>
    {}
  </ol>
</nav>"#,
                    Self::escape_html(id),
                    items_jsx
                )
            }
            A2UIComponent::Textarea {
                id,
                label,
                rows,
            } => {
                let rows_attr = rows
                    .map(|r| format!(r#" rows="{}""#, r))
                    .unwrap_or_default();
                format!(
                    r#"<div>
  <label htmlFor="{}">{}</label>
  <textarea id="{}"{} />
</div>"#,
                    Self::escape_html(id),
                    Self::escape_html(label),
                    Self::escape_html(id),
                    rows_attr
                )
            }
            A2UIComponent::Checkbox { id, label, checked } => {
                let checked_attr = if *checked { " checked" } else { "" };
                format!(
                    r#"<div>
  <input id="{}" type="checkbox"{} />
  <label htmlFor="{}">{}</label>
</div>"#,
                    Self::escape_html(id),
                    checked_attr,
                    Self::escape_html(id),
                    Self::escape_html(label)
                )
            }
            A2UIComponent::Radio {
                id,
                label,
                value,
                checked,
            } => {
                let checked_attr = if *checked { " checked" } else { "" };
                format!(
                    r#"<div>
  <input id="{}" type="radio" value="{}"{} />
  <label htmlFor="{}">{}</label>
</div>"#,
                    Self::escape_html(id),
                    Self::escape_html(value),
                    checked_attr,
                    Self::escape_html(id),
                    Self::escape_html(label)
                )
            }
            A2UIComponent::Card {
                id,
                title,
                children,
            } => {
                let title_jsx = title
                    .as_ref()
                    .map(|t| format!(r#"<h3>{}</h3>"#, Self::escape_html(t)))
                    .unwrap_or_default();
                let children_jsx = children
                    .iter()
                    .map(|child| Self::render_jsx(child))
                    .collect::<Vec<_>>()
                    .join("\n  ");
                format!(
                    r#"<div id="{}" className="card">
  {}
  {}
</div>"#,
                    Self::escape_html(id),
                    title_jsx,
                    children_jsx
                )
            }
            A2UIComponent::Grid {
                id,
                columns,
                children,
            } => {
                let children_jsx = children
                    .iter()
                    .map(|child| Self::render_jsx(child))
                    .collect::<Vec<_>>()
                    .join("\n  ");
                format!(
                    r#"<div id="{}" className="grid" style={{{{ gridTemplateColumns: "repeat({}, 1fr)" }}}}>
  {}
</div>"#,
                    Self::escape_html(id),
                    columns,
                    children_jsx
                )
            }
        }
    }

    pub fn render_native(component: &A2UIComponent) -> String {
        match component {
            A2UIComponent::Button { label, .. } => {
                format!(r#"<Button>{}</Button>"#, Self::escape_html(label))
            }
            A2UIComponent::Input { label, .. } => {
                format!(
                    r#"<TextInput placeholder="{}" />"#,
                    Self::escape_html(label)
                )
            }
            A2UIComponent::Text { content, .. } => {
                format!(r#"<Text>{}</Text>"#, Self::escape_html(content))
            }
            _ => Self::render_jsx(component),
        }
    }

    pub fn inject_aria(html: &str) -> String {
        let mut result = html.to_string();

        // Inject aria-label on buttons without text
        if result.contains("<button") && !result.contains("aria-label") {
            result = result.replace("<button", "<button aria-label=\"button\"");
        }

        // Inject aria-describedby on inputs
        if result.contains("<input") && !result.contains("aria-") {
            result = result.replace(
                "<input",
                "<input aria-describedby=\"input-description\"",
            );
        }

        // Inject role="dialog" on modal divs
        if result.contains("modal") && !result.contains("role=") {
            result = result.replace(
                "id=\"modal",
                "role=\"dialog\" id=\"modal",
            );
        }

        result
    }

    fn escape_html(text: &str) -> String {
        text.replace('&', "&amp;")
            .replace('<', "&lt;")
            .replace('>', "&gt;")
            .replace('"', "&quot;")
            .replace('\'', "&#39;")
    }
}
