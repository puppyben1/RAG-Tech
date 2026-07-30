const DEFAULT_API_BASE = "http://127.0.0.1:8000";

export function getInitialApiBase() {
  return localStorage.getItem("apiBase") || DEFAULT_API_BASE;
}

export function saveApiBase(apiBase) {
  localStorage.setItem("apiBase", apiBase);
}

export async function apiRequest(apiBase, path, payload) {
  const init = payload
    ? {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify(payload),
      }
    : {};
  const response = await fetch(`${apiBase}${path}`, init);
  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(text || `HTTP ${response.status}`);
  }
  if (!response.ok) {
    throw new Error(data.detail || data.error || `HTTP ${response.status}`);
  }
  return data;
}

export function shortPath(path) {
  const parts = String(path || "").split(/[\\/]/);
  return parts.slice(-1)[0] || "-";
}
