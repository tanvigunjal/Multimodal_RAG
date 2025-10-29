// js/ChatService.js
import { API_BASE_URL } from './api.js';

/**
 * Manages communication with the backend RAG API for streaming responses.
 */
export const ChatService = {
  /**
   * @param {object} options
   * @param {string} options.query - The user's query.
   * @param {boolean} options.rich - Whether to request the rich SSE stream.
   * @param {function(Array): void} options.onSources - Callback for when sources are received.
   * @param {function(string): void} options.onToken - Callback for each new token.
   * @param {function(string): void} options.onEnd - Callback when the stream finishes.
   * @param {function(Error): void} options.onError - Callback for any errors.
   * @returns {{close: function}} - An object with a method to manually close the connection.
   */
  streamQuery({ query, rich, onSources, onToken, onEnd, onError }) {
    const endpoint = rich ? 'stream-rich' : 'stream-text';
    const url = `${API_BASE_URL}/query/${endpoint}`;
    
    // For rich streaming, we use EventSource which is ideal for SSE but only supports GET.
    // For simple text, we use POST with fetch to support potentially long queries.
    if (rich) {
      // NOTE: Using EventSource requires the backend to correctly set the content-type 
      // as 'text/event-stream' and to send data in the proper SSE format.
      const eventSource = new EventSource(`${url}?query=${encodeURIComponent(query)}`);
      let fullResponse = '';

      // Custom event listener for 'sources' event from the backend
      eventSource.addEventListener('sources', (event) => {
        try {
          // The backend should send a JSON string of the sources array
          const sources = JSON.parse(event.data);
          if (onSources) onSources(sources);
        } catch (e) {
          console.error('Failed to parse sources event:', e);
        }
      });

      // Event listener for streaming text tokens
      eventSource.addEventListener('token', (event) => {
        // The token is sent as a JSON string
        const token = JSON.parse(event.data); 
        fullResponse += token;
        if (onToken) onToken(token);
      });

      // Event listener for stream completion
      eventSource.addEventListener('end', () => {
        eventSource.close();
        if (onEnd) onEnd(fullResponse);
      });

      // Generic error handling for EventSource
      eventSource.onerror = (err) => {
        console.error('EventSource failed:', err);
        eventSource.close();
        if (onError) onError(new Error('Connection to the server was lost.'));
      };

      return { close: () => eventSource.close() };

    } else {
      // Standard fetch/POST for simple text stream
      const controller = new AbortController();
      const signal = controller.signal;

      (async () => {
        try {
          const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query }),
            signal,
          });

          if (!response.ok || !response.body) {
            const errData = await response.json();
            throw new Error(errData.detail || `HTTP error! Status: ${response.status}`);
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let fullResponse = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value, { stream: true });
            fullResponse += chunk;
            if (onToken) onToken(chunk);
          }
          if (onEnd) onEnd(fullResponse);
        } catch (error) {
          if (error.name !== 'AbortError') {
            console.error('Fetch stream failed:', error);
            if (onError) onError(error);
          }
        }
      })();

      return { close: () => controller.abort() };
    }
  }
};