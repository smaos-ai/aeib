/**
 * Unit tests for Form Handler
 * Tests form submission, SSE routing, state persistence
 */

import {
  attachFormHandlers,
  submitForm,
  handleFormResponse,
  setupSSEListener,
} from './form-handler.js';

describe('Form Handler', () => {
  let mockFetch;
  let mockEventSource;

  beforeEach(() => {
    // Mock fetch
    mockFetch = jest.fn();
    global.fetch = mockFetch;

    // Mock EventSource
    mockEventSource = {
      addEventListener: jest.fn(),
      close: jest.fn(),
    };
    global.EventSource = jest.fn(() => mockEventSource);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  // === FORM SUBMISSION ===

  describe('Form Submission', () => {
    test('submitForm sends JSON to correct endpoint', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 202,
      });

      const formData = { input1: 'value1', checkbox1: true };
      await submitForm('agent-123', 'form-456', formData);

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/agents/agent-123/form-submit',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            form_id: 'form-456',
            values: formData,
          }),
        })
      );
    });

    test('submitForm handles 202 Accepted response', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 202,
      });

      const result = await submitForm('agent-123', 'form-456', {});
      expect(result).toEqual({ ok: true, status: 202 });
    });

    test('submitForm throws on network error', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'));

      await expect(submitForm('agent-123', 'form-456', {})).rejects.toThrow(
        'Network error'
      );
    });

    test('submitForm includes correct form_id', async () => {
      mockFetch.mockResolvedValue({ ok: true });

      await submitForm('agent-abc', 'my-form', { data: 'value' });

      const call = mockFetch.mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.form_id).toBe('my-form');
    });
  });

  // === FORM RESPONSE HANDLING ===

  describe('Form Response Handling', () => {
    test('handleFormResponse parses JSON correctly', () => {
      const event = {
        data: JSON.stringify({
          form_id: 'form-456',
          response: { status: 'ok' },
        }),
      };

      const result = handleFormResponse(event);
      expect(result).toEqual({
        form_id: 'form-456',
        response: { status: 'ok' },
      });
    });

    test('handleFormResponse returns null for invalid JSON', () => {
      const event = {
        data: 'not valid json {',
      };

      const result = handleFormResponse(event);
      expect(result).toBeNull();
    });

    test('handleFormResponse extracts form_id for routing', () => {
      const event = {
        data: JSON.stringify({
          form_id: 'target-form',
          payload: { result: 'success' },
        }),
      };

      const result = handleFormResponse(event);
      expect(result.form_id).toBe('target-form');
    });
  });

  // === SSE LISTENER ===

  describe('SSE Listener Setup', () => {
    test('setupSSEListener connects to SSE endpoint', () => {
      const callback = jest.fn();
      setupSSEListener(callback);

      expect(global.EventSource).toHaveBeenCalledWith('/api/agents/stream');
    });

    test('setupSSEListener attaches message handler', () => {
      const callback = jest.fn();
      setupSSEListener(callback);

      expect(mockEventSource.addEventListener).toHaveBeenCalledWith(
        'message',
        expect.any(Function)
      );
    });

    test('setupSSEListener calls callback on message', () => {
      const callback = jest.fn();
      setupSSEListener(callback);

      // Get the message handler that was attached
      const call = mockEventSource.addEventListener.mock.calls.find(
        c => c[0] === 'message'
      );
      const messageHandler = call[1];

      // Simulate an event
      const event = {
        data: JSON.stringify({
          event_type: 'form_submission',
          form_id: 'test-form',
          values: { key: 'value' },
        }),
      };
      messageHandler(event);

      expect(callback).toHaveBeenCalled();
    });

    test('setupSSEListener handles attach error handler', () => {
      setupSSEListener(jest.fn());

      expect(mockEventSource.addEventListener).toHaveBeenCalledWith(
        'error',
        expect.any(Function)
      );
    });
  });

  // === FORM ATTACHMENT ===

  describe('Form Handler Attachment', () => {
    test('attachFormHandlers prevents default submit', () => {
      const form = document.createElement('form');
      form.id = 'test-form';
      form.innerHTML = '<input id="field1" value="test" />';
      document.body.appendChild(form);

      const submitEvent = new Event('submit');
      submitEvent.preventDefault = jest.fn();

      mockFetch.mockResolvedValue({ ok: true });

      attachFormHandlers(form, 'agent-123');
      form.dispatchEvent(submitEvent);

      expect(submitEvent.preventDefault).toHaveBeenCalled();
      document.body.removeChild(form);
    });

    test('attachFormHandlers extracts form data', async () => {
      const form = document.createElement('form');
      form.id = 'test-form';
      form.innerHTML = `
        <input id="input1" value="alice" />
        <input id="input2" type="checkbox" checked />
        <select id="select1"><option value="opt1" selected>Option 1</option></select>
      `;
      document.body.appendChild(form);

      mockFetch.mockResolvedValue({ ok: true });

      attachFormHandlers(form, 'agent-123');

      const submitEvent = new Event('submit');
      form.dispatchEvent(submitEvent);

      await new Promise(resolve => setTimeout(resolve, 0));

      const fetchCall = mockFetch.mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);
      expect(body.values.input1).toBe('alice');
      expect(body.values.input2).toBe(true);

      document.body.removeChild(form);
    });

    test('attachFormHandlers passes correct agent ID', async () => {
      const form = document.createElement('form');
      form.id = 'test-form';
      form.innerHTML = '<input id="field1" value="test" />';
      document.body.appendChild(form);

      mockFetch.mockResolvedValue({ ok: true });

      attachFormHandlers(form, 'my-agent-id');
      form.dispatchEvent(new Event('submit'));

      await new Promise(resolve => setTimeout(resolve, 0));

      const fetchCall = mockFetch.mock.calls[0];
      expect(fetchCall[0]).toContain('my-agent-id');

      document.body.removeChild(form);
    });
  });

  // === ERROR HANDLING ===

  describe('Error Handling', () => {
    test('submitForm handles HTTP errors gracefully', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
      });

      const result = await submitForm('agent-123', 'form-456', {});
      expect(result.ok).toBe(false);
    });

    test('setupSSEListener logs errors', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      const callback = jest.fn();

      setupSSEListener(callback);

      // Get the error handler
      const errorCall = mockEventSource.addEventListener.mock.calls.find(
        c => c[0] === 'error'
      );
      const errorHandler = errorCall[1];

      errorHandler(new Event('error'));

      expect(consoleSpy).toHaveBeenCalledWith(
        'SSE connection error',
        expect.anything()
      );

      consoleSpy.mockRestore();
    });

    test('attachFormHandlers handles missing fields', async () => {
      const form = document.createElement('form');
      form.id = 'test-form';
      form.innerHTML = '<input id="field1" />'; // No value attribute
      document.body.appendChild(form);

      mockFetch.mockResolvedValue({ ok: true });

      attachFormHandlers(form, 'agent-123');
      form.dispatchEvent(new Event('submit'));

      await new Promise(resolve => setTimeout(resolve, 0));

      expect(mockFetch).toHaveBeenCalled();

      document.body.removeChild(form);
    });
  });

  // === RESPONSE ROUTING ===

  describe('Response Routing', () => {
    test('form responses are routed by form_id', () => {
      const event1Data = {
        form_id: 'form-1',
        values: { result: 'from-form-1' },
      };

      const event2Data = {
        form_id: 'form-2',
        values: { result: 'from-form-2' },
      };

      const response1 = handleFormResponse({
        data: JSON.stringify(event1Data),
      });
      const response2 = handleFormResponse({
        data: JSON.stringify(event2Data),
      });

      expect(response1.form_id).toBe('form-1');
      expect(response2.form_id).toBe('form-2');
      expect(response1.values.result).toBe('from-form-1');
      expect(response2.values.result).toBe('from-form-2');
    });

    test('responses without form_id are handled gracefully', () => {
      const event = {
        data: JSON.stringify({
          event_type: 'some_event',
          payload: 'data',
        }),
      };

      const result = handleFormResponse(event);
      expect(result).toEqual({
        event_type: 'some_event',
        payload: 'data',
      });
    });
  });

  // === INTEGRATION ===

  describe('Integration', () => {
    test('complete flow: form submission and response', async () => {
      const form = document.createElement('form');
      form.id = 'approval-form';
      form.innerHTML = `
        <input id="approved" type="checkbox" checked />
        <button type="submit">Submit</button>
      `;
      document.body.appendChild(form);

      mockFetch.mockResolvedValue({ ok: true, status: 202 });

      // Attach handlers
      attachFormHandlers(form, 'agent-abc');

      // Submit form
      form.dispatchEvent(new Event('submit'));

      // Wait for async
      await new Promise(resolve => setTimeout(resolve, 10));

      // Verify fetch was called
      expect(mockFetch).toHaveBeenCalled();
      const fetchCall = mockFetch.mock.calls[0];
      expect(fetchCall[0]).toContain('agent-abc');
      expect(fetchCall[0]).toContain('/api/agents/');
      expect(fetchCall[0]).toContain('/form-submit');

      document.body.removeChild(form);
    });
  });
});
