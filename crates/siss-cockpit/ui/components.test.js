/**
 * Unit tests for A2UI Component Renderer
 * Tests all 18 component types: rendering, state management, validation
 */

import { renderComponent, createFormComponent, createFormState } from './components.js';

describe('A2UI Component Renderer', () => {
  // === DISPLAY COMPONENTS (8 types) ===

  describe('Display Components', () => {
    test('renders Text component with content', () => {
      const comp = {
        type: 'text',
        id: 'text-1',
        content: 'Hello World',
        size: 'md',
      };
      const html = renderComponent(comp);
      expect(html).toContain('Hello World');
      expect(html.tagName).toBe('DIV');
    });

    test('renders Badge component with color', () => {
      const comp = {
        type: 'badge',
        id: 'badge-1',
        label: 'Active',
        color: 'green',
      };
      const html = renderComponent(comp);
      expect(html).toContain('Active');
      expect(html.className).toContain('badge');
    });

    test('renders Alert component with level', () => {
      const comp = {
        type: 'alert',
        id: 'alert-1',
        message: 'Warning: Action required',
        level: 'warn',
      };
      const html = renderComponent(comp);
      expect(html).toContain('Warning: Action required');
      expect(html.className).toContain('alert');
    });

    test('renders Progress bar with value and max', () => {
      const comp = {
        type: 'progress',
        id: 'prog-1',
        value: 50,
        max: 100,
        label: 'Loading',
      };
      const html = renderComponent(comp);
      expect(html).toContain('Loading');
      expect(html.className).toContain('progress');
    });

    test('renders Divider component', () => {
      const comp = {
        type: 'divider',
        id: 'div-1',
      };
      const html = renderComponent(comp);
      expect(html.tagName).toBe('HR');
    });

    test('renders Link component with href', () => {
      const comp = {
        type: 'link',
        id: 'link-1',
        label: 'Click here',
        href: 'https://example.com',
      };
      const html = renderComponent(comp);
      expect(html).toContain('Click here');
      expect(html.href).toBe('https://example.com/');
    });

    test('renders Tooltip component', () => {
      const comp = {
        type: 'tooltip',
        id: 'tooltip-1',
        text: 'Hover me',
        content: 'Tooltip content',
      };
      const html = renderComponent(comp);
      expect(html).toContain('Hover me');
      expect(html.title).toBe('Tooltip content');
    });

    test('renders Breadcrumb component with items', () => {
      const comp = {
        type: 'breadcrumb',
        id: 'bread-1',
        items: ['Home', 'Products', 'Electronics'],
      };
      const html = renderComponent(comp);
      expect(html).toContain('Home');
      expect(html).toContain('Products');
      expect(html).toContain('Electronics');
    });
  });

  // === FORM COMPONENTS (6 types) ===

  describe('Form Components', () => {
    test('renders Input component with label and placeholder', () => {
      const comp = {
        type: 'input',
        id: 'input-1',
        label: 'Username',
        placeholder: 'Enter name',
        required: true,
      };
      const html = renderComponent(comp);
      expect(html.tagName).toBe('DIV');
      expect(html.textContent).toContain('Username');
    });

    test('renders Textarea component with rows', () => {
      const comp = {
        type: 'textarea',
        id: 'textarea-1',
        label: 'Comments',
        rows: 5,
      };
      const html = renderComponent(comp);
      expect(html).toContain('Comments');
      expect(html.tagName).toBe('DIV');
    });

    test('renders Select component with options', () => {
      const comp = {
        type: 'select',
        id: 'select-1',
        label: 'Choose option',
        options: [
          { value: 'a', label: 'Option A' },
          { value: 'b', label: 'Option B' },
        ],
      };
      const html = renderComponent(comp);
      expect(html).toContain('Choose option');
      expect(html).toContain('Option A');
      expect(html).toContain('Option B');
    });

    test('renders Checkbox component', () => {
      const comp = {
        type: 'checkbox',
        id: 'check-1',
        label: 'Agree to terms',
        checked: false,
      };
      const html = renderComponent(comp);
      expect(html).toContain('Agree to terms');
    });

    test('renders Radio component with options', () => {
      const comp = {
        type: 'radio',
        id: 'radio-1',
        label: 'Select one',
        value: 'option1',
        checked: false,
      };
      const html = renderComponent(comp);
      expect(html).toContain('Select one');
    });

    test('renders Button component', () => {
      const comp = {
        type: 'button',
        id: 'btn-1',
        label: 'Submit',
        action: 'submit',
      };
      const html = renderComponent(comp);
      expect(html.tagName).toBe('BUTTON');
      expect(html).toContain('Submit');
    });
  });

  // === LAYOUT COMPONENTS (4 types) ===

  describe('Layout Components', () => {
    test('renders Card component with title and children', () => {
      const comp = {
        type: 'card',
        id: 'card-1',
        title: 'Card Title',
        children: [
          { type: 'text', id: 't-1', content: 'Content inside' },
        ],
      };
      const html = renderComponent(comp);
      expect(html).toContain('Card Title');
      expect(html).toContain('Content inside');
    });

    test('renders Grid component with columns', () => {
      const comp = {
        type: 'grid',
        id: 'grid-1',
        columns: 2,
        children: [
          { type: 'text', id: 't-1', content: 'Cell 1' },
          { type: 'text', id: 't-2', content: 'Cell 2' },
        ],
      };
      const html = renderComponent(comp);
      expect(html).toContain('Cell 1');
      expect(html).toContain('Cell 2');
      expect(html.style.gridTemplateColumns).toContain('repeat(2');
    });

    test('renders Modal component with title and content', () => {
      const comp = {
        type: 'modal',
        id: 'modal-1',
        title: 'Confirmation',
        content: 'Are you sure?',
        children: [],
      };
      const html = renderComponent(comp);
      expect(html).toContain('Confirmation');
      expect(html).toContain('Are you sure?');
      expect(html.className).toContain('modal');
    });

    test('renders Table component with headers and rows', () => {
      const comp = {
        type: 'table',
        id: 'table-1',
        headers: ['Name', 'Status'],
        rows: [
          ['Alice', 'Active'],
          ['Bob', 'Inactive'],
        ],
      };
      const html = renderComponent(comp);
      expect(html.tagName).toBe('TABLE');
      expect(html.textContent).toContain('Name');
      expect(html.textContent).toContain('Alice');
      expect(html.textContent).toContain('Inactive');
    });
  });

  // === STATE MANAGEMENT ===

  describe('Form State Management', () => {
    test('createFormState initializes with empty values', () => {
      const components = [
        { type: 'input', id: 'input-1', label: 'Name' },
        { type: 'checkbox', id: 'check-1', label: 'Agree' },
      ];
      const state = createFormState(components);
      expect(state.values['input-1']).toBe('');
      expect(state.values['check-1']).toBe(false);
    });

    test('createFormState updates field value', () => {
      const state = createFormState([
        { type: 'input', id: 'input-1', label: 'Name' },
      ]);
      state.setValue('input-1', 'Alice');
      expect(state.values['input-1']).toBe('Alice');
    });

    test('createFormState validates required fields', () => {
      const state = createFormState([
        { type: 'input', id: 'input-1', label: 'Name', required: true },
      ]);
      const errors = state.validate();
      expect(errors).toHaveProperty('input-1');
    });

    test('createFormState returns form data as JSON', () => {
      const state = createFormState([
        { type: 'input', id: 'input-1', label: 'Name' },
        { type: 'checkbox', id: 'check-1', label: 'Agree' },
      ]);
      state.setValue('input-1', 'Alice');
      state.setValue('check-1', true);
      const data = state.toJSON();
      expect(data['input-1']).toBe('Alice');
      expect(data['check-1']).toBe(true);
    });
  });

  // === ERROR HANDLING ===

  describe('Error Handling', () => {
    test('gracefully handles unknown component type', () => {
      const comp = {
        type: 'unknown',
        id: 'unknown-1',
      };
      const html = renderComponent(comp);
      expect(html).toBeTruthy();
      expect(html.className).toContain('fallback');
    });

    test('handles missing required fields', () => {
      const comp = {
        type: 'input',
        id: 'input-1',
        // missing label
      };
      const html = renderComponent(comp);
      expect(html).toBeTruthy(); // Should not crash
    });

    test('handles nested children with missing components', () => {
      const comp = {
        type: 'card',
        id: 'card-1',
        title: 'Card',
        children: [
          { type: 'unknown', id: 'x' },
        ],
      };
      const html = renderComponent(comp);
      expect(html).toBeTruthy();
    });
  });

  // === INTERACTION ===

  describe('Component Interaction', () => {
    test('Input component updates state on change', () => {
      const comp = {
        type: 'input',
        id: 'input-1',
        label: 'Name',
      };
      const state = createFormState([comp]);
      const html = renderComponent(comp);
      const input = html.querySelector('input');

      // Simulate user input
      input.value = 'Test Name';
      input.dispatchEvent(new Event('change', { bubbles: true }));

      // State should be updated via handler
      expect(state.values['input-1']).toBe('Test Name');
    });

    test('Button component is clickable', () => {
      const comp = {
        type: 'button',
        id: 'btn-1',
        label: 'Click me',
        action: 'submit',
      };
      const html = renderComponent(comp);
      const btn = html;

      expect(btn.disabled).toBe(false);
      expect(btn.onclick).toBeTruthy();
    });

    test('Checkbox component toggles state', () => {
      const comp = {
        type: 'checkbox',
        id: 'check-1',
        label: 'Agree',
        checked: false,
      };
      const state = createFormState([comp]);
      const html = renderComponent(comp);
      const checkbox = html.querySelector('input[type="checkbox"]');

      checkbox.checked = true;
      checkbox.dispatchEvent(new Event('change', { bubbles: true }));

      expect(state.values['check-1']).toBe(true);
    });
  });
});
