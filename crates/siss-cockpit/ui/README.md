# A2UI Component Library

Complete JavaScript implementation for rendering 18 A2UIComponent primitives from agent event streams.

## Files

- **components.js** — Component renderer for all 18 A2UI types + form state management
- **components.test.js** — Unit tests for all components (15+ test cases)
- **form-handler.js** — Form submission, SSE listening, and response routing
- **form-handler.test.js** — Form handler tests (20+ test cases)
- **components.css** — Styling for all components
- **README.md** — This file

## Component Types (18 Total)

### Display Components (8)
1. **Text** — Plain text with size variants
2. **Badge** — Label with color
3. **Alert** — Message with level (info/warn/error)
4. **Progress** — Progress bar with value/max
5. **Divider** — Horizontal rule
6. **Link** — Hyperlink
7. **Tooltip** — Hover tooltip
8. **Breadcrumb** — Navigation breadcrumb

### Form Components (6)
9. **Input** — Text input field
10. **Textarea** — Multi-line text area
11. **Select** — Dropdown selector
12. **Checkbox** — Boolean checkbox
13. **Radio** — Radio button
14. **Button** — Clickable button

### Layout Components (4)
15. **Card** — Container with optional title
16. **Grid** — Multi-column grid layout
17. **Modal** — Dialog overlay
18. **Table** — Data table with headers/rows

## Usage

### Rendering a Component

```javascript
import { renderComponent } from './components.js';

const comp = {
  type: 'input',
  id: 'username-field',
  label: 'Username',
  placeholder: 'Enter your name',
  required: true,
};

const domElement = renderComponent(comp);
document.body.appendChild(domElement);
```

### Form State Management

```javascript
import { createFormState } from './components.js';

const components = [
  { type: 'input', id: 'name', label: 'Name', required: true },
  { type: 'checkbox', id: 'agree', label: 'I agree' },
];

const state = createFormState(components);
state.setValue('name', 'Alice');
state.setValue('agree', true);

const errors = state.validate(); // {} if valid
const data = state.toJSON(); // { name: 'Alice', agree: true }
```

### Form Submission

```javascript
import { attachFormHandlers, submitForm } from './form-handler.js';

const form = document.querySelector('#my-form');
attachFormHandlers(form, 'agent-uuid-here');

// Form will automatically submit to /api/agents/{agentId}/form-submit
// on submit event
```

### SSE Listener

```javascript
import { setupSSEListener } from './form-handler.js';

setupSSEListener((event) => {
  if (event.event_type === 'form_response') {
    console.log('Form response:', event);
  }
});
```

### Complete Integration

```javascript
import { renderComponent, createFormComponent } from './components.js';
import { attachFormHandlers } from './form-handler.js';

// Define form
const formDef = {
  id: 'approval-form',
  components: [
    {
      type: 'text',
      id: 't1',
      content: 'Approve this action?',
      size: 'lg',
    },
    {
      type: 'button',
      id: 'btn-yes',
      label: 'Approve',
      action: 'submit',
    },
    {
      type: 'button',
      id: 'btn-no',
      label: 'Reject',
      action: 'submit',
    },
  ],
};

// Create form component
const form = createFormComponent(formDef);
const element = form.render();
document.body.appendChild(element);

// Attach handlers
attachFormHandlers(element, 'agent-123');

// On submit, form data is sent to /api/agents/agent-123/form-submit
// and response comes back via SSE
```

## API Reference

### renderComponent(comp)
Renders a single A2UIComponent to a DOM element.

**Parameters:**
- `comp` (Object) — Component definition with `type` and type-specific fields

**Returns:** HTMLElement

**Throws:** Never (returns fallback on unknown type)

### createFormState(components)
Creates a form state manager.

**Parameters:**
- `components` (Array) — Array of form component definitions

**Returns:** Object with methods:
- `setValue(fieldId, value)` — Set field value
- `validate()` — Validate all fields, returns errors object
- `toJSON()` — Get all values as object

### createFormComponent(formDef)
Creates a complete form component with state.

**Parameters:**
- `formDef` (Object) — Form definition with `components` array

**Returns:** Object with methods:
- `render()` — Returns HTMLElement form
- `getData()` — Get form values
- `validate()` — Validate form

### submitForm(agentId, formId, values)
Submit form data to backend.

**Parameters:**
- `agentId` (string) — Agent UUID
- `formId` (string) — Form identifier
- `values` (Object) — Form values

**Returns:** Promise<Response>

### attachFormHandlers(form, agentId)
Attach submit handlers to a form element.

**Parameters:**
- `form` (HTMLElement) — Form element
- `agentId` (string) — Agent UUID

**Returns:** void

### setupSSEListener(onMessage)
Setup SSE listener for form responses.

**Parameters:**
- `onMessage` (Function) — Callback for each message

**Returns:** EventSource

## Testing

Run tests with Jest:

```bash
npm test components.test.js
npm test form-handler.test.js
```

Test coverage:
- **components.test.js** — 15+ tests covering all 18 component types
- **form-handler.test.js** — 20+ tests for submission, routing, error handling

## Styling

Import CSS in your HTML:

```html
<link rel="stylesheet" href="components.css">
```

All components use CSS classes prefixed with `a2ui-` for scoping.

Dark theme by default, with support for:
- Light/dark mode
- High contrast
- Reduced motion
- Responsive design

## Error Handling

- Unknown component types render as alert fallback
- Missing required fields are validated before submission
- Network errors are logged to console
- Invalid JSON is gracefully skipped

## Browser Support

- Chrome/Chromium (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

Requires ES6 modules.

## License

Part of SISS Phase 32 A2UI implementation.
