// js/theme.js

export function initTheme() {
  const themeToggle = document.getElementById('theme-toggle');
  if (!themeToggle) {
    console.error('Theme toggle button not found!');
    return;
  }
  
  const KEY = 'app-theme';
  // Media query to check for OS-level dark mode preference
  const prefersDarkMQ = window.matchMedia('(prefers-color-scheme: dark)');
  
  // Determine the initial theme
  const savedTheme = localStorage.getItem(KEY);
  let currentTheme = savedTheme || (prefersDarkMQ.matches ? 'dark' : 'light');

  /**
   * Applies a given theme to the app.
   * @param {string} theme - 'light' or 'dark'
   */
  const applyTheme = (theme) => {
    document.documentElement.setAttribute('data-theme', theme);
    // Sync the toggle switch's state with the current theme
    themeToggle.checked = theme === 'dark';
  };

  // Listen for changes on the toggle switch
  themeToggle.addEventListener('change', () => {
    currentTheme = themeToggle.checked ? 'dark' : 'light';
    localStorage.setItem(KEY, currentTheme); // Save the user's choice
    applyTheme(currentTheme);
  });

  // Listen for changes in OS preference
  prefersDarkMQ.addEventListener('change', (e) => {
    // Only change the theme if the user hasn't explicitly set one
    if (!localStorage.getItem(KEY)) {
      currentTheme = e.matches ? 'dark' : 'light';
      applyTheme(currentTheme);
    }
  });

  // Apply the initial theme when the script loads
  applyTheme(currentTheme);
}