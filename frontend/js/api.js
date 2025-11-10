// js/api.js
export const API_BASE_URL = '/v1';
export const AUTH_BASE_URL = '/v1/auth';
export const API_ORIGIN = '';

// Load token from local storage
let authToken = localStorage.getItem('auth_token');

export function setAuthToken(token) {
    authToken = token;
    localStorage.setItem('auth_token', token);
}

export function getAuthToken() {
    return authToken;
}

export function clearAuthToken() {
    authToken = null;
    localStorage.removeItem('auth_token');
}

function getApiUrl(path) {
    return `${API_ORIGIN}${path}`;
}

export async function login(email, password) {
    const response = await api(getApiUrl(`${AUTH_BASE_URL}/login`), {
        method: 'POST',
        body: JSON.stringify({ email, password })
    });
    setAuthToken(response.token);
    return response;
}

export async function api(url, opts = {}, timeoutMs = 30000) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);

    // Ensure we have the right content type for JSON requests
    if (opts.body && typeof opts.body === 'string') {
        opts.headers = {
            ...opts.headers,
            'Content-Type': 'application/json'
        };
    }
    
    // Add authorization header if token exists
    if (authToken && !url.includes('/login')) {
        opts.headers = {
            ...opts.headers,
            'Authorization': `Bearer ${authToken}`
        };
    }
    
    try {
        // Ensure the URL has the correct origin
        const fullUrl = url.startsWith('http') ? url : `${API_ORIGIN}${url}`;
        console.log('Making API request to:', fullUrl, opts);
        
        const res = await fetch(fullUrl, { ...opts, signal: ctrl.signal });
        console.log('API response status:', res.status);
        
        // Handle 401 Unauthorized before parsing response
        if (res.status === 401) {
            clearAuthToken();
            window.location.href = `${window.location.origin}/login.html`;
            return;
        }
        
        // Parse response
        const text = await res.text();
        let data;
        try {
            data = JSON.parse(text);
            console.log('API response parsed:', data);
        } catch (e) {
            console.log('Response is not JSON:', text);
            data = text;
        }
        
        // Handle error responses
        if (!res.ok) {
            const errorMessage = typeof data === 'object' ? data?.detail : `${res.status} ${res.statusText}`;
            console.error('API error:', errorMessage);
            throw new Error(errorMessage);
        }
        
        return data;
    } finally {
        clearTimeout(t);
    }
}



export async function checkAuth() {
    if (!authToken) {
        return false;
    }
    try {
        await api(getApiUrl(`${AUTH_BASE_URL}/me`));
        return true;
    } catch (error) {
        clearAuthToken();
        return false;
    }
}

export async function logout() {
    clearAuthToken();
    window.location.href = '/login';
}

export async function getChatTitle(query, chatId) {
    const { title } = await api(getApiUrl(`${API_BASE_URL}/query/summarize`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
    });
    return { title, chatId };
}
