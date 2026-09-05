/**
 * Form Handler for A2UI Components
 * Manages form submission, SSE-based responses, and state persistence
 */

/**
 * Submit form data to cockpit backend
 * @param {string} agentId - Agent UUID
 * @param {string} formId - Form identifier
 * @param {Object} values - Form values object
 * @returns {Promise<Response>} Fetch response
 */
export async function submitForm(agentId, formId, values) {
  const url = `/api/agents/${agentId}/form-submit`;
  const payload = {
    form_id: formId,
    values: values,
  };

  return fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

/**
 * Parse form response from SSE event
 * @param {Event} event - SSE message event
 * @returns {Object|null} Parsed response or null if invalid JSON
 */
export function handleFormResponse(event) {
  try {
    return JSON.parse(event.data);
  } catch (e) {
    console.warn('Failed to parse form response:', e);
    return null;
  }
}

/**
 * Setup SSE listener for form responses
 * @param {Function} onMessage - Callback for each SSE message
 * @returns {EventSource} EventSource instance
 */
export function setupSSEListener(onMessage) {
  const es = new EventSource('/api/agents/stream');

  es.addEventListener('message', (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.warn('Failed to parse SSE message:', e);
    }
  });

  es.addEventListener('error', (event) => {
    console.error('SSE connection error', event);
  });

  return es;
}

/**
 * Attach form submit handlers to a form element
 * Intercepts form submission and sends via POST
 * @param {HTMLFormElement} form - Form element
 * @param {string} agentId - Agent UUID
 * @returns {void}
 */
export function attachFormHandlers(form, agentId) {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Collect form data
    const formData = new FormData(form);
    const values = {};

    for (const [key, value] of formData.entries()) {
      // Handle checkbox specially
      const field = form.querySelector(`[name="${key}"]`);
      if (field && field.type === 'checkbox') {
        values[key] = field.checked;
      } else {
        values[key] = value;
      }
    }

    // Collect all input/select/textarea fields including those without name
    form.querySelectorAll('input, select, textarea').forEach(field => {
      if (!field.name && field.id) {
        // Use id if name is not available
        if (field.type === 'checkbox') {
          values[field.id] = field.checked;
        } else if (field.type === 'radio') {
          if (field.checked) {
            values[field.id] = field.value;
          }
        } else {
          values[field.id] = field.value;
        }
      }
    });

    try {
      const response = await submitForm(agentId, form.id, values);

      if (!response.ok) {
        console.error('Form submission failed:', response.status, response.statusText);
        // Could show error UI here
      }
    } catch (err) {
      console.error('Form submission error:', err);
      // Could show error UI here
    }
  });
}

/**
 * Initialize form handling for dashboard
 * Sets up SSE listener and attaches handlers to all forms
 * @param {string} agentId - Current agent ID (optional, can be per-form)
 * @returns {Object} Handler object with setup methods
 */
export function initializeFormHandling(agentId) {
  // Track active forms
  const activeForms = new Map();

  // Setup SSE listener
  const es = setupSSEListener((event) => {
    if (event.form_id && activeForms.has(event.form_id)) {
      const handler = activeForms.get(event.form_id);
      if (handler.onResponse) {
        handler.onResponse(event);
      }
    }
  });

  return {
    /**
     * Register a form with the handler
     * @param {HTMLFormElement} form - Form element
     * @param {string} formAgentId - Agent ID for this form (overrides default)
     * @param {Function} onResponse - Callback for form response
     */
    registerForm(form, formAgentId, onResponse) {
      const id = form.id || 'form-' + Math.random().toString(36).substr(2, 9);
      form.id = id;

      activeForms.set(id, {
        form,
        agentId: formAgentId || agentId,
        onResponse,
      });

      attachFormHandlers(form, formAgentId || agentId);
    },

    /**
     * Unregister a form
     * @param {string} formId - Form ID to unregister
     */
    unregisterForm(formId) {
      activeForms.delete(formId);
    },

    /**
     * Close SSE connection
     */
    close() {
      es.close();
    },
  };
}

/**
 * Utility: Extract form data from a form element
 * @param {HTMLFormElement} form - Form element
 * @returns {Object} Form data
 */
export function extractFormData(form) {
  const data = {};

  form.querySelectorAll('input, select, textarea').forEach(field => {
    const fieldId = field.name || field.id;
    if (!fieldId) return;

    if (field.type === 'checkbox') {
      data[fieldId] = field.checked;
    } else if (field.type === 'radio') {
      if (field.checked) {
        data[fieldId] = field.value;
      }
    } else {
      data[fieldId] = field.value || '';
    }
  });

  return data;
}

/**
 * Utility: Validate form data against A2UI schema
 * @param {Object} formData - Form data to validate
 * @param {Array} components - Original A2UI components
 * @returns {Object} Validation errors (empty if valid)
 */
export function validateFormData(formData, components) {
  const errors = {};

  components.forEach(comp => {
    if (comp.required && !formData[comp.id]) {
      errors[comp.id] = `${comp.label || 'Field'} is required`;
    }
  });

  return errors;
}

/**
 * Utility: Format form data for submission
 * Ensures all values are properly typed and encoded
 * @param {Object} data - Raw form data
 * @returns {Object} Formatted data
 */
export function formatFormData(data) {
  const formatted = {};

  for (const [key, value] of Object.entries(data)) {
    if (value === null || value === undefined) {
      formatted[key] = '';
    } else if (typeof value === 'string') {
      formatted[key] = value.trim();
    } else {
      formatted[key] = value;
    }
  }

  return formatted;
}

export default {
  submitForm,
  handleFormResponse,
  setupSSEListener,
  attachFormHandlers,
  initializeFormHandling,
  extractFormData,
  validateFormData,
  formatFormData,
};
