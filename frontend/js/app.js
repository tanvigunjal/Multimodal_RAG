// js/app.js
import { initTheme } from './theme.js';
import { initChat } from './chat.js';
import { initUploads } from './uploads.js';
import { initSidebar } from './sidebar.js';

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initChat();
  initUploads();
  initSidebar();
});