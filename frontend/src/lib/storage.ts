export type StoredAuth = {
  accessToken: string;
  refreshToken: string;
};

const AUTH_STORAGE_KEY = "fastapi-chuxue.auth";

export function getStoredAuth(): StoredAuth | null {
  const rawValue = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (!rawValue) {
    return null;
  }

  try {
    return JSON.parse(rawValue) as StoredAuth;
  } catch {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

export function setStoredAuth(auth: StoredAuth): void {
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
}

export function clearStoredAuth(): void {
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
}
