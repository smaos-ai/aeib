/**
 * A2UI Component Renderer
 * Renders all 18 A2UIComponent primitives to DOM nodes
 */

/**
 * Render a single A2UIComponent to a DOM node
 * @param {Object} comp - Component object with type and properties
 * @returns {HTMLElement} DOM node representing the component
 */
export function renderComponent(comp) {
  if (!comp || !comp.type) {
    return renderFallback('Invalid component structure');
  }

  const type = comp.type.toLowerCase();

  // === DISPLAY COMPONENTS (8 types) ===
  if (type === 'text') return renderText(comp);
  if (type === 'badge') return renderBadge(comp);
  if (type === 'alert') return renderAlert(comp);
  if (type === 'progress') return renderProgress(comp);
  if (type === 'divider') return renderDivider(comp);
  if (type === 'link') return renderLink(comp);
  if (type === 'tooltip') return renderTooltip(comp);
  if (type === 'breadcrumb') return renderBreadcrumb(comp);

  // === FORM COMPONENTS (6 types) ===
  if (type === 'input') return renderInput(comp);
  if (type === 'textarea') return renderTextarea(comp);
  if (type === 'select') return renderSelect(comp);
  if (type === 'checkbox') return renderCheckbox(comp);
  if (type === 'radio') return renderRadio(comp);
  if (type === 'button') return renderButton(comp);

  // === LAYOUT COMPONENTS (4 types) ===
  if (type === 'card') return renderCard(comp);
  if (type === 'grid') return renderGrid(comp);
  if (type === 'modal') return renderModal(comp);
  if (type === 'table') return renderTable(comp);

  // Unknown type
  return renderFallback(`Unknown component type: ${comp.type}`);
}

// === DISPLAY COMPONENTS ===

function renderText(comp) {
  const div = document.createElement('div');
  div.className = `a2ui-text a2ui-text-${comp.size || 'md'}`;
  div.textContent = comp.content || '';
  div.id = comp.id || '';
  return div;
}

function renderBadge(comp) {
  const span = document.createElement('span');
  span.className = `a2ui-badge badge-${comp.color || 'blue'}`;
  span.textContent = comp.label || '';
  span.id = comp.id || '';
  return span;
}

function renderAlert(comp) {
  const div = document.createElement('div');
  div.className = `a2ui-alert alert-${comp.level || 'info'}`;
  div.role = 'alert';
  div.id = comp.id || '';

  const icon = document.createElement('span');
  icon.className = 'alert-icon';
  icon.textContent = comp.level === 'error' ? '✕' : comp.level === 'warn' ? '⚠' : 'ⓘ';

  const msg = document.createElement('span');
  msg.className = 'alert-message';
  msg.textContent = comp.message || '';

  div.appendChild(icon);
  div.appendChild(msg);
  return div;
}

function renderProgress(comp) {
  const div = document.createElement('div');
  div.className = 'a2ui-progress-wrapper';
  div.id = comp.id || '';

  const label = document.createElement('div');
  label.className = 'progress-label';
  label.textContent = comp.label || '';

  const bar = document.createElement('div');
  bar.className = 'a2ui-progress-bar';
  const percent = Math.min(100, Math.round((comp.value || 0) / (comp.max || 100) * 100));
  bar.style.width = percent + '%';

  const text = document.createElement('div');
  text.className = 'progress-text';
  text.textContent = percent + '%';

  div.appendChild(label);
  div.appendChild(bar);
  div.appendChild(text);
  return div;
}

function renderDivider(comp) {
  const hr = document.createElement('hr');
  hr.className = 'a2ui-divider';
  hr.id = comp.id || '';
  return hr;
}

function renderLink(comp) {
  const a = document.createElement('a');
  a.className = 'a2ui-link';
  a.href = comp.href || '#';
  a.textContent = comp.label || 'Link';
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.id = comp.id || '';
  return a;
}

function renderTooltip(comp) {
  const span = document.createElement('span');
  span.className = 'a2ui-tooltip';
  span.title = comp.content || '';
  span.textContent = comp.text || '';
  span.id = comp.id || '';
  return span;
}

function renderBreadcrumb(comp) {
  const nav = document.createElement('nav');
  nav.className = 'a2ui-breadcrumb';
  nav.id = comp.id || '';
  nav.setAttribute('aria-label', 'Breadcrumb');

  const list = document.createElement('ol');
  (comp.items || []).forEach((item, idx) => {
    const li = document.createElement('li');
    li.textContent = item;
    if (idx < (comp.items || []).length - 1) {
      li.appendChild(document.createTextNode(' / '));
    }
    list.appendChild(li);
  });

  nav.appendChild(list);
  return nav;
}

// === FORM COMPONENTS ===

function renderInput(comp) {
  const wrapper = document.createElement('div');
  wrapper.className = 'a2ui-form-group';
  wrapper.id = comp.id || '';

  const label = document.createElement('label');
  label.className = 'form-label';
  label.setAttribute('for', comp.id || '');
  label.textContent = comp.label || '';
  if (comp.required) {
    const req = document.createElement('span');
    req.className = 'required';
    req.textContent = ' *';
    label.appendChild(req);
  }

  const input = document.createElement('input');
  input.type = 'text';
  input.id = comp.id || '';
  input.className = 'form-input';
  input.placeholder = comp.placeholder || '';
  input.required = comp.required || false;

  wrapper.appendChild(label);
  wrapper.appendChild(input);
  return wrapper;
}

function renderTextarea(comp) {
  const wrapper = document.createElement('div');
  wrapper.className = 'a2ui-form-group';
  wrapper.id = comp.id || '';

  const label = document.createElement('label');
  label.className = 'form-label';
  label.setAttribute('for', comp.id || '');
  label.textContent = comp.label || '';

  const textarea = document.createElement('textarea');
  textarea.id = comp.id || '';
  textarea.className = 'form-textarea';
  textarea.rows = comp.rows || 4;

  wrapper.appendChild(label);
  wrapper.appendChild(textarea);
  return wrapper;
}

function renderSelect(comp) {
  const wrapper = document.createElement('div');
  wrapper.className = 'a2ui-form-group';
  wrapper.id = comp.id || '';

  const label = document.createElement('label');
  label.className = 'form-label';
  label.setAttribute('for', comp.id || '');
  label.textContent = comp.label || '';

  const select = document.createElement('select');
  select.id = comp.id || '';
  select.className = 'form-select';

  (comp.options || []).forEach(opt => {
    const option = document.createElement('option');
    option.value = opt.value || '';
    option.textContent = opt.label || '';
    select.appendChild(option);
  });

  wrapper.appendChild(label);
  wrapper.appendChild(select);
  return wrapper;
}

function renderCheckbox(comp) {
  const wrapper = document.createElement('div');
  wrapper.className = 'a2ui-form-group a2ui-checkbox-wrapper';
  wrapper.id = comp.id || '';

  const input = document.createElement('input');
  input.type = 'checkbox';
  input.id = comp.id || '';
  input.className = 'form-checkbox';
  input.checked = comp.checked || false;

  const label = document.createElement('label');
  label.className = 'checkbox-label';
  label.setAttribute('for', comp.id || '');
  label.textContent = comp.label || '';

  wrapper.appendChild(input);
  wrapper.appendChild(label);
  return wrapper;
}

function renderRadio(comp) {
  const wrapper = document.createElement('div');
  wrapper.className = 'a2ui-form-group a2ui-radio-wrapper';
  wrapper.id = comp.id || '';

  const input = document.createElement('input');
  input.type = 'radio';
  input.name = comp.id || '';
  input.value = comp.value || '';
  input.id = comp.id || '';
  input.className = 'form-radio';
  input.checked = comp.checked || false;

  const label = document.createElement('label');
  label.className = 'radio-label';
  label.setAttribute('for', comp.id || '');
  label.textContent = comp.label || '';

  wrapper.appendChild(input);
  wrapper.appendChild(label);
  return wrapper;
}

function renderButton(comp) {
  const button = document.createElement('button');
  button.type = comp.action === 'reset' ? 'reset' : 'submit';
  button.id = comp.id || '';
  button.className = 'a2ui-button btn-' + (comp.action || 'submit');
  button.textContent = comp.label || 'Button';
  return button;
}

// === LAYOUT COMPONENTS ===

function renderCard(comp) {
  const card = document.createElement('div');
  card.className = 'a2ui-card';
  card.id = comp.id || '';

  if (comp.title) {
    const header = document.createElement('div');
    header.className = 'card-header';
    header.textContent = comp.title;
    card.appendChild(header);
  }

  const body = document.createElement('div');
  body.className = 'card-body';
  (comp.children || []).forEach(child => {
    try {
      body.appendChild(renderComponent(child));
    } catch (e) {
      console.error('Error rendering child in card:', e);
    }
  });

  card.appendChild(body);
  return card;
}

function renderGrid(comp) {
  const grid = document.createElement('div');
  grid.className = 'a2ui-grid';
  grid.id = comp.id || '';
  grid.style.display = 'grid';
  grid.style.gridTemplateColumns = `repeat(${comp.columns || 1}, 1fr)`;
  grid.style.gap = '16px';

  (comp.children || []).forEach(child => {
    try {
      grid.appendChild(renderComponent(child));
    } catch (e) {
      console.error('Error rendering child in grid:', e);
    }
  });

  return grid;
}

function renderModal(comp) {
  const modal = document.createElement('div');
  modal.className = 'a2ui-modal';
  modal.id = comp.id || '';
  modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-labelledby', comp.id + '-title');

  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';

  const content = document.createElement('div');
  content.className = 'modal-content';

  const header = document.createElement('div');
  header.className = 'modal-header';
  const title = document.createElement('h2');
  title.id = comp.id + '-title';
  title.textContent = comp.title || '';
  header.appendChild(title);

  const body = document.createElement('div');
  body.className = 'modal-body';
  if (comp.content) {
    body.textContent = comp.content;
  }
  (comp.children || []).forEach(child => {
    try {
      body.appendChild(renderComponent(child));
    } catch (e) {
      console.error('Error rendering child in modal:', e);
    }
  });

  content.appendChild(header);
  content.appendChild(body);
  modal.appendChild(backdrop);
  modal.appendChild(content);
  return modal;
}

function renderTable(comp) {
  const table = document.createElement('table');
  table.className = 'a2ui-table';
  table.id = comp.id || '';

  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  (comp.headers || []).forEach(h => {
    const th = document.createElement('th');
    th.textContent = h;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);

  const tbody = document.createElement('tbody');
  (comp.rows || []).forEach(row => {
    const tr = document.createElement('tr');
    row.forEach(cell => {
      const td = document.createElement('td');
      td.textContent = cell || '';
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });

  table.appendChild(thead);
  table.appendChild(tbody);
  return table;
}

// === FALLBACK & UTILITIES ===

function renderFallback(message) {
  const div = document.createElement('div');
  div.className = 'a2ui-fallback alert-error';
  div.role = 'alert';
  div.textContent = 'Component error: ' + message;
  return div;
}

/**
 * Create form state manager for a set of form components
 * @param {Array} components - Array of form components
 * @returns {Object} State manager with setValue, validate, toJSON methods
 */
export function createFormState(components) {
  const state = {
    values: {},
    errors: {},

    /**
     * Set a field value
     * @param {string} fieldId - Component id
     * @param {*} value - Field value
     */
    setValue(fieldId, value) {
      this.values[fieldId] = value;
      this.errors[fieldId] = null; // Clear error on change
    },

    /**
     * Validate all fields
     * @returns {Object} Errors object, empty if no errors
     */
    validate() {
      this.errors = {};
      components.forEach(comp => {
        if (comp.required && !this.values[comp.id]) {
          this.errors[comp.id] = `${comp.label || 'Field'} is required`;
        }
      });
      return this.errors;
    },

    /**
     * Get form data as JSON
     * @returns {Object} Form values
     */
    toJSON() {
      return { ...this.values };
    },
  };

  // Initialize values based on component types
  components.forEach(comp => {
    if (comp.type === 'checkbox') {
      state.values[comp.id] = comp.checked || false;
    } else if (comp.type === 'radio') {
      state.values[comp.id] = comp.value || '';
    } else {
      state.values[comp.id] = '';
    }
  });

  return state;
}

/**
 * Create a form component wrapper with state binding
 * @param {Object} formDef - Form definition with components array
 * @returns {Object} Form component with render and submit methods
 */
export function createFormComponent(formDef) {
  const state = createFormState(formDef.components || []);

  return {
    state,

    /**
     * Render the entire form
     * @returns {HTMLElement} Form element
     */
    render() {
      const form = document.createElement('form');
      form.className = 'a2ui-form';
      form.id = formDef.id || '';

      (formDef.components || []).forEach(comp => {
        const el = renderComponent(comp);

        // Bind input handlers
        const input = el.querySelector('input, textarea, select');
        if (input) {
          input.addEventListener('change', (e) => {
            if (e.target.type === 'checkbox') {
              state.setValue(e.target.id, e.target.checked);
            } else {
              state.setValue(e.target.id, e.target.value);
            }
          });
        }

        form.appendChild(el);
      });

      return form;
    },

    /**
     * Get form data
     * @returns {Object} Form values
     */
    getData() {
      return state.toJSON();
    },

    /**
     * Validate form
     * @returns {boolean} True if valid
     */
    validate() {
      return Object.keys(state.validate()).length === 0;
    },
  };
}

export default {
  renderComponent,
  createFormState,
  createFormComponent,
};
