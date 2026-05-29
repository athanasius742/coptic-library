/**
 * Mock-user store — a deliberately tiny "is the reader signed in" seam, backed
 * by localStorage with NO real authentication, session, or backend. This is a
 * stand-in so the logged-in / logged-out branches (home shelf, profile,
 * progress tracking) are real and demonstrable now; a later, separate effort
 * replaces it with a real account model + auth + login page. Keep the surface
 * small so swapping `useMockUser` for a real session hook is a clean change.
 *
 * Default state: signed OUT. SSR-safe + error-swallowing, like the other
 * localStorage stores.
 */

export type MockUser = {
  name: string;
  signedInAt: number;
};

// Versioned key so the eventual real-auth migration can detect/clear it.
const STORAGE_KEY = "mock-user-v1";

export function getMockUser(): MockUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && typeof parsed.name === "string") {
      return parsed as MockUser;
    }
  } catch {
    // malformed / unavailable — treat as signed out.
  }
  return null;
}

/** Sign in the mock user. `name` defaults to a generic "Reader" if omitted. */
export function signIn(name = "Reader"): MockUser {
  const user: MockUser = { name: name.trim() || "Reader", signedInAt: Date.now() };
  if (typeof window !== "undefined") {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    } catch {
      // ignore — sign-in still applies in-memory for this session.
    }
  }
  return user;
}

export function signOut(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

export { STORAGE_KEY as MOCK_USER_KEY };
