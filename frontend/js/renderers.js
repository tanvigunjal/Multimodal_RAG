// js/renderers.js
import { API_BASE_URL } from './api.js';

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

  // Only handle sources once
  const uniqueSources = [...new Map(sources.map(s => [`${s.file_name}:${s.page_number}`, s])).values()];
  
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
      if (!acc[source.file_name]) {
        acc[source.file_name] = {
          type: source.type,
          pages: [],
          file_path: source.file_path // Store the file path from metadata
        };
      }
      acc[source.file_name].pages.push(source.page_number);
      return acc;
    }, {});

    // Create source list items
    Object.entries(groupedSources).forEach(([fileName, data]) => {
      const item = document.createElement('div');
      item.className = 'source-list-item';
      
      // Sort page numbers numerically
      const sortedPages = data.pages.sort((a, b) => a - b);
      const pagesText = sortedPages.join(', ');
      
      // Create a clickable link for PDF files
      const sourceContent = fileName.toLowerCase().endsWith('.pdf') ? 
        (() => {
          // Function to extract sha256 subfolder and create PDF path
          const getPdfPath = (filePath, fileName) => {
            // Try to extract from docker path format first
            const dockerMatch = filePath.match(/\/uploads\/([a-f0-9]{8})[^/]*\/([^/]+\.pdf)$/i);
            if (dockerMatch) {
              return `${dockerMatch[1]}/${dockerMatch[2]}`;
            }
            
            // Try to extract from relative path format
            const relativeMatch = filePath.match(/uploads\/([a-f0-9]{8})[^/]*\/([^/]+\.pdf)$/i);
            if (relativeMatch) {
              return `${relativeMatch[1]}/${relativeMatch[2]}`;
            }
            
            // Try to use the filename if it starts with a sha256 prefix
            const sha256Match = fileName.match(/^([a-f0-9]{8})[^/]*/i);
            if (sha256Match) {
              return `${sha256Match[1]}/${fileName}`;
            }
            
            // Default fallback with known sha256 prefix
            console.warn('No sha256 prefix found, using default:', { fileName, filePath });
            return `83beb169/${fileName}`;
          };
          
          const filePath = data.file_path || '';
          const pdfPath = getPdfPath(filePath, fileName);
          console.log('Constructed PDF path:', pdfPath);
          
          return `<a href="${API_BASE_URL}/pdf?path=${encodeURIComponent(pdfPath)}" target="_blank" class="source-link">
           <i class="fas fa-file-pdf"></i>
           <span class="source-text">${fileName} (page ${pagesText})</span>
           <i class="fas fa-external-link-alt"></i>
         </a>`;
        })() :
        `<i class="fas fa-${data.type === 'image' ? 'image' : 'file-alt'}"></i>
         <span class="source-text">${fileName} (page ${pagesText})</span>`;
      
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
  overlay.className = 'image-popup-overlay';
  
  const popup = document.createElement('div');
  popup.className = 'image-popup';
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