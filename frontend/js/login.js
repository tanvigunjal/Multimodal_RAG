import { login, checkAuth } from './api.js';

// Initialize login page
async function initLoginPage() {
    // Check if user is already logged in
    const isAuthenticated = await checkAuth();
    if (isAuthenticated) {
        window.location.href = '/';
        return;
    }
    
    // Add event listeners
    const form = document.getElementById('login-form');
    form.addEventListener('submit', handleLogin);
    
    const toggleBtn = document.querySelector('.toggle-password');
    toggleBtn.addEventListener('click', handlePasswordToggle);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initLoginPage);

// Function to handle password visibility toggle
function handlePasswordToggle() {
    const passwordInput = document.getElementById('password');
    const toggleBtn = document.querySelector('.toggle-password i');
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleBtn.className = 'fas fa-eye-slash';
    } else {
        passwordInput.type = 'password';
        toggleBtn.className = 'fas fa-eye';
    }
}

// Function to handle login
async function handleLogin(event) {
    event.preventDefault();
    
    // Get form elements
    const email = document.getElementById('email');
    const password = document.getElementById('password');
    const emailError = document.getElementById('email-error');
    const passwordError = document.getElementById('password-error');
    const loginError = document.getElementById('login-error');
    
    // Reset error messages
    emailError.textContent = '';
    passwordError.textContent = '';
    
    // Validate email
    if (!email.value.match(/.*@gmail\.com$/)) {
        emailError.textContent = 'Please enter a valid Gmail address';
        return false;
    }
    
    // Validate password
    if (password.value.length < 8) {
        passwordError.textContent = 'Password must be at least 8 characters long';
        return false;
    }
    
    try {
        // Clear all error messages
        emailError.textContent = '';
        passwordError.textContent = '';
        loginError.textContent = '';
        
        // Attempt to login with the API
        console.log('Attempting login with:', email.value);
        const response = await login(email.value, password.value);
        console.log('Login response:', response);
        
        if (response && response.token) {
            // Store token in localStorage
            localStorage.setItem('authToken', response.token);
            window.location.href = `${window.location.origin}/`;
        } else {
            loginError.textContent = 'Invalid login response from server';
        }
    } catch (error) {
        console.error('Login error:', error);
        loginError.textContent = error.message || 'Login failed. Please try again.';
    }
    return false;
}

