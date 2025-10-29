// js/api.js
export const API_BASE_URL = '/v1';
export const API_ORIGIN = window.location.origin;

export async function api(url, opts = {}, timeoutMs = 30000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...opts, signal: ctrl.signal });
    const text = await res.text();
    let data = null;
    try { data = JSON.parse(text); } catch { /* not JSON */ }
    if (!res.ok) throw new Error(data?.detail || `${res.status} ${res.statusText}`);
    return data ?? text;
  } finally {
    clearTimeout(t);
  }
}

export async function getChatTitle(query, chatId) {
  const { title } = await api(`${API_BASE_URL}/query/summarize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  return { title, chatId };
}
