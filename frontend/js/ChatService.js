// // js/ChatService.js
// import { API_BASE_URL } from './api.js';

// /**
//  * Manages communication with the backend RAG API for streaming responses.
//  */
// export const ChatService = {
//   /**
//    * @param {object} options
//    * @param {string} options.query - The user's query.
//    * @param {boolean} options.rich - Whether to request the rich SSE stream.
//    * @param {function(Array): void} options.onSources - Callback for when sources are received.
//    * @param {function(string): void} options.onToken - Callback for each new token.
//    * @param {function(string): void} options.onEnd - Callback when the stream finishes.
//    * @param {function(Error): void} options.onError - Callback for any errors.
//    * @returns {{close: function}} - An object with a method to manually close the connection.
//    */
//   streamQuery({ query, rich, onSources, onToken, onEnd, onError }) {
//     const endpoint = rich ? 'stream-rich' : 'stream-text';
//     const url = `${API_BASE_URL}/query/${endpoint}`;
    
//     // For rich streaming, we use EventSource which is ideal for SSE but only supports GET.
//     // For simple text, we use POST with fetch to support potentially long queries.
//     if (rich) {
//       // Get auth token from localStorage
//       const authToken = localStorage.getItem('auth_token');
//       if (!authToken) {
//         if (onError) onError(new Error('Not authenticated. Please log in.'));
//         return { close: () => {} };
//       }
      
//       let fullResponse = '';
//       let eventSource = null;

//       try {
//         // Create EventSource with auth token in URL
//         eventSource = new EventSource(
//           `${url}?query=${encodeURIComponent(query)}&token=${encodeURIComponent(authToken)}`
//         );

//       // Handler for 'sources' event
//       const handleSources = (event) => {
//         try {
//           if (!event.data) {
//             console.warn('Empty sources event data');
//             return;
//           }

//           const sources = JSON.parse(event.data);
//           console.log('Received sources event:', sources);
          
//           if (!Array.isArray(sources)) {
//             console.error('Sources is not an array:', sources);
//             return;
//           }
          
//           const validSources = sources.filter(s => {
//             if (!s || typeof s !== 'object') return false;
//             return s.file_name || s.file_path;
//           });
          
//           console.log('Processed valid sources:', validSources);
          
//           if (onSources && validSources.length > 0) {
//             onSources(validSources);
//           }
//         } catch (e) {
//           console.error('Failed to process sources event:', e, event.data);
//           handleError(new Event('error', { error: e }));
//         }
//       };

//       // Handler for 'token' event
//       const handleToken = (event) => {
//         try {
//           if (!event.data) return;
//           const token = JSON.parse(event.data);
//           if (typeof token === 'string') {
//             fullResponse += token;
//             if (onToken) onToken(token);
//           }
//         } catch (e) {
//           console.error('Failed to process token event:', e, event.data);
//           // Don't fail the whole stream for a single token error
//         }
//       };

//       // Cleanup function
//       const cleanup = () => {
//         if (!eventSource) return;
//         try {
//           eventSource.removeEventListener('sources', handleSources);
//           eventSource.removeEventListener('token', handleToken);
//           eventSource.removeEventListener('end', handleEnd);
//           eventSource.removeEventListener('error', handleError);
//           eventSource.close();
//           eventSource = null;
//         } catch (e) {
//           console.warn('Error during EventSource cleanup:', e);
//         }
//       };

//       // Handler for 'end' event
//       const handleEnd = () => {
//         if (onEnd) onEnd(fullResponse);
//         cleanup();
//       };

//       // Error handler for EventSource
//       const handleError = (event) => {
//         if (!eventSource || eventSource.readyState === EventSource.CLOSED) {
//           console.log('EventSource connection closed normally');
//           return;
//         }

//         // Get detailed error information
//         let errorMessage = 'Connection to the server was lost';
//         try {
//           if (event && event.data) {
//             const errorData = JSON.parse(event.data);
//             errorMessage = errorData.detail || errorMessage;
//           }
//         } catch (e) {
//           console.warn('Failed to parse error data:', e);
//         }

//         console.error('Stream error:', errorMessage);
//         cleanup();
//         if (onError) onError(new Error(errorMessage));
//       };

//       // Set up event listeners
//       eventSource.addEventListener('sources', handleSources);
//       eventSource.addEventListener('token', handleToken);
//       eventSource.addEventListener('end', handleEnd);
//       eventSource.onerror = handleError;
      
//       // Return cleanup function
//       return { close: cleanup };

//       } catch (e) {
//         console.error('Error setting up EventSource:', e);
//         if (eventSource) {
//           try {
//             eventSource.close();
//           } catch (closeError) {
//             console.warn('Error closing EventSource:', closeError);
//           }
//         }
//         if (onError) onError(e);
//         return { close: () => {} };
//       }

//       // Set up event listeners and error handling
//       eventSource.addEventListener('sources', handleSources);
//       eventSource.addEventListener('token', handleToken);
//       eventSource.addEventListener('end', handleEnd);
//       eventSource.onerror = handleError;
      
//       // Return cleanup function
//       return {
//         close: () => {
//           try {
//             eventSource.removeEventListener('sources', handleSources);
//             eventSource.removeEventListener('token', handleToken);
//             eventSource.removeEventListener('end', handleEnd);
//             eventSource.removeEventListener('error', handleError);
//             eventSource.close();
//           } catch (e) {
//             console.warn('Error during manual EventSource cleanup:', e);
//           }
//         }
//       };

//     } else {
//       // Standard fetch/POST for simple text stream
//       const controller = new AbortController();
//       const signal = controller.signal;

//       (async () => {
//         try {
//           const authToken = localStorage.getItem('auth_token');
//           if (!authToken) {
//             const authError = new Error("Error: Not authenticated. Missing Authorization header or 'token' query parameter.");
//             console.error(authError.message);
//             if (onError) onError(authError);
//             return;
//           }

//           const response = await fetch(url, {
//             method: 'POST',
//             headers: { 
//               'Content-Type': 'application/json',
//               'Authorization': `Bearer ${authToken}`
//             },
//             body: JSON.stringify({ query }),
//             signal,
//           });

//           if (!response.ok || !response.body) {
//             const error = await response.json().catch(() => ({ detail: `HTTP error! Status: ${response.status}` }));
//             throw new Error(error.detail || `Request failed: ${response.status}`);
//           }

//           const reader = response.body.getReader();
//           const decoder = new TextDecoder();
//           let fullResponse = '';

//           while (true) {
//             const { done, value } = await reader.read();
//             if (done) break;
//             const chunk = decoder.decode(value, { stream: true });
//             fullResponse += chunk;
//             if (onToken) onToken(chunk);
//           }
//           if (onEnd) onEnd(fullResponse);
//         } catch (error) {
//           // Only report errors that aren't from manual stream closing
//           if (error.name !== 'AbortError') {
//             const errorMessage = error.message || 'Failed to stream response';
//             console.error('Stream error:', errorMessage);
//             if (onError) onError(new Error(errorMessage));
//           }
//         } finally {
//           // Ensure reader is released if it exists
//           if (reader) {
//             try {
//               await reader.cancel();
//             } catch (e) {
//               console.warn('Failed to cancel reader:', e);
//             }
//           }
//         }
//       })();

//       return { 
//         close: () => {
//           controller.abort();
//           console.log('Stream closed by user');
//         }
//       };
//     }
//   }
// };


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
      // Get auth token from localStorage - FIXED: Changed from 'auth_token' to 'authToken'
      const authToken = localStorage.getItem('authToken');
      if (!authToken) {
        if (onError) onError(new Error('Not authenticated. Please log in.'));
        return { close: () => {} };
      }
      
      let fullResponse = '';
      let eventSource = null;

      try {
        // Create EventSource with auth token in URL
        eventSource = new EventSource(
          `${url}?query=${encodeURIComponent(query)}&token=${encodeURIComponent(authToken)}`
        );

        // Handler for 'sources' event
        const handleSources = (event) => {
          try {
            if (!event.data) {
              console.warn('Empty sources event data');
              return;
            }

            const sources = JSON.parse(event.data);
            console.log('Received sources event:', sources);
            
            if (!Array.isArray(sources)) {
              console.error('Sources is not an array:', sources);
              return;
            }
            
            const validSources = sources.filter(s => {
              if (!s || typeof s !== 'object') return false;
              return s.file_name || s.file_path;
            });
            
            console.log('Processed valid sources:', validSources);
            
            if (onSources && validSources.length > 0) {
              onSources(validSources);
            }
          } catch (e) {
            console.error('Failed to process sources event:', e, event.data);
            handleError(new Event('error', { error: e }));
          }
        };

        // Handler for 'token' event
        const handleToken = (event) => {
          try {
            if (!event.data) return;
            const token = JSON.parse(event.data);
            if (typeof token === 'string') {
              fullResponse += token;
              if (onToken) onToken(token);
            }
          } catch (e) {
            console.error('Failed to process token event:', e, event.data);
            // Don't fail the whole stream for a single token error
          }
        };

        // Cleanup function
        const cleanup = () => {
          if (!eventSource) return;
          try {
            eventSource.removeEventListener('sources', handleSources);
            eventSource.removeEventListener('token', handleToken);
            eventSource.removeEventListener('end', handleEnd);
            eventSource.removeEventListener('error', handleError);
            eventSource.close();
            eventSource = null;
          } catch (e) {
            console.warn('Error during EventSource cleanup:', e);
          }
        };

        // Handler for 'end' event
        const handleEnd = () => {
          if (onEnd) onEnd(fullResponse);
          cleanup();
        };

        // Error handler for EventSource
        const handleError = (event) => {
          if (!eventSource || eventSource.readyState === EventSource.CLOSED) {
            console.log('EventSource connection closed normally');
            return;
          }

          // Get detailed error information
          let errorMessage = 'Connection to the server was lost';
          try {
            if (event && event.data) {
              const errorData = JSON.parse(event.data);
              errorMessage = errorData.detail || errorMessage;
            }
          } catch (e) {
            console.warn('Failed to parse error data:', e);
          }

          console.error('Stream error:', errorMessage);
          cleanup();
          if (onError) onError(new Error(errorMessage));
        };

        // Set up event listeners
        eventSource.addEventListener('sources', handleSources);
        eventSource.addEventListener('token', handleToken);
        eventSource.addEventListener('end', handleEnd);
        eventSource.onerror = handleError;
        
        // Return cleanup function
        return { close: cleanup };

      } catch (e) {
        console.error('Error setting up EventSource:', e);
        if (eventSource) {
          try {
            eventSource.close();
          } catch (closeError) {
            console.warn('Error closing EventSource:', closeError);
          }
        }
        if (onError) onError(e);
        return { close: () => {} };
      }

    } else {
      // Standard fetch/POST for simple text stream
      const controller = new AbortController();
      const signal = controller.signal;

      (async () => {
        try {
          // FIXED: Changed from 'auth_token' to 'authToken'
          const authToken = localStorage.getItem('authToken');
          if (!authToken) {
            const authError = new Error("Error: Not authenticated. Missing Authorization header or 'token' query parameter.");
            console.error(authError.message);
            if (onError) onError(authError);
            return;
          }

          const response = await fetch(url, {
            method: 'POST',
            headers: { 
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({ query }),
            signal,
          });

          if (!response.ok || !response.body) {
            const error = await response.json().catch(() => ({ detail: `HTTP error! Status: ${response.status}` }));
            throw new Error(error.detail || `Request failed: ${response.status}`);
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
          // Only report errors that aren't from manual stream closing
          if (error.name !== 'AbortError') {
            const errorMessage = error.message || 'Failed to stream response';
            console.error('Stream error:', errorMessage);
            if (onError) onError(new Error(errorMessage));
          }
        }
      })();

      return { 
        close: () => {
          controller.abort();
          console.log('Stream closed by user');
        }
      };
    }
  }
};