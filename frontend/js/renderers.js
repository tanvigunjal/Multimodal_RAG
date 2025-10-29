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

  // 1. Render Visuals First (if available)
  const images = sources.filter(s => s.type === 'image' && s.image_path);
  const tables = sources.filter(s => s.type === 'table' && s.content);

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
        img.alt = `Image from ${source.file_name}`;
        img.loading = 'lazy';
        img.addEventListener('click', () => openImagePopup(imageUrl));
        const caption = document.createElement('figcaption');
        caption.textContent = `${source.file_name} (p. ${source.page_number})`;
        card.appendChild(img);
        card.appendChild(caption);
        grid.appendChild(card);
      });
      visualsContainer.appendChild(grid);
    }

    if (tables.length > 0) {
      tables.forEach(source => {
        const item = document.createElement('div');
        item.className = 'source-item';
        // We are removing the title from here to match the new design
        // item.innerHTML = `<strong>Table from: ${source.file_name} (p. ${source.page_number})</strong>`;
        const tableContainer = document.createElement('div');
        tableContainer.innerHTML = DOMPurify.sanitize(source.content);
        item.appendChild(tableContainer);
        visualsContainer.appendChild(item);
      });
    }
    contentDiv.appendChild(visualsContainer);
  }

  // 2. Render the Answer Text
  const cleanedText = text.replace(/\[\d+\]/g, '').trim();
  const answerHtml = DOMPurify.sanitize(marked.parse(cleanedText));
  const answerDiv = document.createElement('div');
  answerDiv.className = 'answer-text';
  answerDiv.innerHTML = answerHtml;
  if (streaming) {
    answerDiv.classList.add('streaming');
  }
  contentDiv.appendChild(answerDiv);

  // 3. Render the Collapsible Sources Section
  const uniqueSources = [...new Map(sources.map(s => [`${s.file_name}:${s.page_number}`, s])).values()];
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

    uniqueSources.forEach(source => {
      const item = document.createElement('div');
      item.className = 'source-list-item';
      item.innerHTML = `
        <i class="fas fa-file-alt"></i>
        <span class="source-text">${source.file_name}, page ${source.page_number}</span>
      `;
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