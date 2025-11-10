// js/init.js
import { checkAuth, logout } from './api.js';
import { initChat } from './chat.js';
import { initUploads } from './uploads.js';
import { initSidebar } from './sidebar.js';

export async function initializeApp() {
    try {
        // Check authentication
        const isAuthenticated = await checkAuth();
        if (!isAuthenticated) {
            window.location.href = '/login.html';
            return;
        }

        // Initialize all components
        initChat();
        initUploads();
        initSidebar();

        // Add logout handler
        document.getElementById('logout-btn').addEventListener('click', logout);

        // Show the app after initialization
        document.querySelector('.app-frame').style.visibility = 'visible';
    } catch (error) {
        console.error('Error initializing app:', error);
        window.location.href = '/login.html';
    }
}