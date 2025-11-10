// js/renderers.js
import { API_BASE_URL, getAuthToken } from './api.js';

/**
 * A consolidated function to render the entire bot message, including visuals,
 * text, and a collapsible sources section, in a specific order.
 * @param {HTMLElement} contentDiv - The message div to append content to.
 * @param {object} data - The data for rendering.
 * @param {string} [data.text] - The raw text from the API.
 * @param {Array} [data.sources] - The array of source objects.
 * @param {boolean} [data.streaming=false] - Whether the text is currently streaming.
 */
export function renderBotMessage(contentDiv, { text = '', sources = [], streaming = false }) {
  // Clear previous content
  contentDiv.innerHTML = '';

  // Validate and normalize sources array
  const normalizedSources = Array.isArray(sources) ? sources : [];
  
  // Filter out invalid sources and normalize required fields
  const validSources = normalizedSources.filter(s => {
    if (!s || typeof s !== 'object') return false;
    
    // Ensure required fields have default values
    s.file_name = s.file_name || 'Unknown Document';
    s.type = s.type || 'text';
    s.page_number = s.page_number || 1;
    
    // PDF sources must have a file path
    if (s.file_name.toLowerCase().endsWith('.pdf') && !s.file_path) {
      console.warn('PDF source missing file path:', s.file_name);
      return false;
    }
    
    return true;
  });
  
  // Create unique sources based on content identifier
  const uniqueSources = [...new Map(validSources.map(s => {
    const contentId = s.file_path ? 
      `${s.file_path}:${s.page_number}` : 
      `${s.file_name}:${s.page_number}`;
    return [contentId, s];
  })).values()];
  
  console.log('Sources processing:', {
    input: sources?.length || 0,
    valid: validSources.length,
    unique: uniqueSources.length
  });
  
  // 1. Render Visuals First (if available)
  const images = uniqueSources.filter(s => s.type === 'image' && s.image_path);
  const tables = uniqueSources.filter(s => s.type === 'table' && s.content);

  if (images.length > 0 || tables.length > 0) {
    const visualsContainer = document.createElement('div');
    visualsContainer.className = 'visuals-container';

    if (images.length > 0) {
      const grid = document.createElement('div');
      grid.className = 'image-grid';
      images.forEach(source => {
        const card = document.createElement('figure');
        card.className = 'image-card';
        const imageUrl = `${API_BASE_URL}/image?path=${encodeURIComponent(source.image_path)}`;
        const img = document.createElement('img');
        img.src = imageUrl;
        img.alt = 'Image';
        img.loading = 'lazy';
        img.addEventListener('click', () => openImagePopup(imageUrl));
        card.appendChild(img);
        grid.appendChild(card);
      });
      visualsContainer.appendChild(grid);
    }

    if (tables.length > 0) {
      tables.forEach(source => {
        const item = document.createElement('div');
        item.className = 'source-item table-container';
        const tableContainer = document.createElement('div');
        tableContainer.innerHTML = DOMPurify.sanitize(source.content);
        item.appendChild(tableContainer);
        visualsContainer.appendChild(item);
      });
    }
    contentDiv.appendChild(visualsContainer);
  }

  // 2. Render the Answer Text
  // Remove line containing Sources:
  const cleanedText = text
    .replace(/Sources:.*\n?/, '') // Remove "Sources:" line
    .replace(/.*\.pdf.*\n?/g, '') // Remove any line containing .pdf
    .replace(/\[\d+\]/g, '')
    .trim();

  // Parse the markdown and sanitize
  const parsedHtml = DOMPurify.sanitize(marked.parse(cleanedText));
  
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message bot';
  
  const answerDiv = document.createElement('div');
  answerDiv.className = 'answer-text';
  answerDiv.innerHTML = parsedHtml;
  if (streaming) {
    answerDiv.classList.add('streaming');
  }
  
  messageDiv.appendChild(answerDiv);
  contentDiv.appendChild(messageDiv);

  // 3. Render the Collapsible Sources Section
  if (uniqueSources.length > 0) {
    const sourcesWrapper = document.createElement('div');
    sourcesWrapper.className = 'sources-accordion';

    const button = document.createElement('button');
    button.className = 'accordion-button';
    button.innerHTML = `
      <i class="fas fa-book"></i>
      <span>Sources (${uniqueSources.length})</span>
      <i class="fas fa-chevron-down"></i>
    `;
    
    const panel = document.createElement('div');
    panel.className = 'accordion-panel';
    const sourceList = document.createElement('div');
    sourceList.className = 'sources-list';

    // Group sources by file name and path
    const groupedSources = uniqueSources.reduce((acc, source) => {
      // Skip invalid sources
      if (!source || (!source.file_name && !source.file_path)) {
        console.warn('Invalid source found:', source);
        return acc;
      }

      // Use file path as identifier if available, otherwise fallback to file name
      const fileId = source.file_path || source.file_name || 'unknown';
      const fileName = source.file_name || 'Unknown Document';

      if (!acc[fileId]) {
        acc[fileId] = {
          type: source.type || 'text',
          pages: [],
          file_name: fileName,
          file_path: source.file_path
        };
      }
      
      // Only add valid page numbers
      if (source.page_number != null && source.page_number !== undefined) {
        acc[fileId].pages.push(source.page_number);
      }
      
      return acc;
    }, {});

    // Create source list items
    Object.entries(groupedSources).forEach(([fileId, data]) => {
      const item = document.createElement('div');
      item.className = 'source-list-item';
      
      // Ensure we have valid display values
      const displayName = data.file_name || 'Unknown Document';
      const pageNumbers = data.pages.filter(p => p != null && p !== undefined);
      const pagesText = pageNumbers.length > 0 ? pageNumbers.sort((a, b) => a - b).join(', ') : '1';      // Create a clickable link for PDF files
      const sourceContent = (data.file_name || '').toLowerCase().endsWith('.pdf') ? 
        (() => {
          const fullPath = data.file_path; // Full path from backend
          const displayName = data.file_name || 'Unknown Document';
          const token = getAuthToken(); // Use the API helper function
          
          // Extract the required path format: '<sha256_subfolder>/<filename>'
          let pdfPath = null;
          if (fullPath) {
            const match = fullPath.match(/\/uploads\/([^/]+\/[^/]+)$/);
            pdfPath = match ? match[1] : null;
          }
          
          if (!pdfPath || !token) {
            const reason = !pdfPath ? 'Invalid file path format' : 'Not authenticated';
            console.warn(`Cannot create PDF link: ${reason}`, { fullPath });
            return `<div class="source-link disabled">
              <i class="fas fa-file-pdf"></i>
              <span class="source-text"><strong>${displayName}</strong> (Page ${pagesText})</span>
              ${!token ? '<i class="fas fa-exclamation-circle" title="Please log in to view PDFs"></i>' : ''}
            </div>`;
          }
          
          try {
            const pdfUrl = `${API_BASE_URL}/pdf?path=${encodeURIComponent(pdfPath)}&token=${encodeURIComponent(token)}`;
            console.log('Generated PDF URL:', { pdfPath, pdfUrl });
            return `<a href="${pdfUrl}" target="_blank" class="source-link">
              <i class="fas fa-file-pdf"></i>
              <span class="source-text"><strong>${displayName}</strong> (Page ${pagesText})</span>
              <i class="fas fa-external-link-alt"></i>
            </a>`;
          } catch (error) {
            console.error('Error generating PDF link:', error);
            return `<div class="source-link disabled">
              <i class="fas fa-file-pdf"></i>
              <span class="source-text"><strong>${displayName}</strong> (Page ${pagesText})</span>
              <i class="fas fa-exclamation-circle" title="Error generating PDF link"></i>
            </div>`;
          }`;`;
        })() :
        `<i class="fas fa-${data.type === 'image' ? 'image' : 'file-alt'}"></i>
         <span class="source-text"><strong>${data.file_name || 'Unknown Document'}</strong> (Page ${pagesText})</span>`;
      
      item.innerHTML = sourceContent;
      sourceList.appendChild(item);
    });

    panel.appendChild(sourceList);
    sourcesWrapper.appendChild(button);
    sourcesWrapper.appendChild(panel);

    button.addEventListener('click', () => {
      sourcesWrapper.classList.toggle('active');
      const icon = button.querySelector('.fa-chevron-down');
      icon.style.transform = sourcesWrapper.classList.contains('active') ? 'rotate(180deg)' : 'rotate(0deg)';
      panel.style.maxHeight = sourcesWrapper.classList.contains('active') ? panel.scrollHeight + "px" : null;
    });
    contentDiv.appendChild(sourcesWrapper);
  }
}

/**
 * Opens a modal popup to display a larger version of an image.
 * @param {string} url - The URL of the image to display.
 */
export function openImagePopup(url) {
  const existing = document.querySelector('.image-popup-overlay');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.className = 'image-popup-overlay fade-in';
  
  const popup = document.createElement('div');
  popup.className = 'image-popup scale-in';
  const img = document.createElement('img');
  img.src = url;
  popup.appendChild(img);
  
  const closeBtn = document.createElement('button');
  closeBtn.className = 'popup-close';
  closeBtn.innerHTML = '&times;';
  
  overlay.appendChild(popup);
  overlay.appendChild(closeBtn);
  
  const close = () => overlay.remove();
  closeBtn.addEventListener('click', close);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) close();
  });
  
  document.body.appendChild(overlay);
}