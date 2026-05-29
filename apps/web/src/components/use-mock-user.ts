"use client";

import { useEffect, useState } from "react";

import {
  getMockUser,
  MOCK_USER_KEY,
  type MockUser,
  signIn as signInStore,
  signOut as signOutStore,
} from "@/lib/mock-user";

/**
 * The one place the rest of the UI touches the mock-user seam. Mirrors the
 * theme-toggle idiom: SSR + first client render report "signed out" (the
 * neutral state the server can know), then a `mounted` effect reads the real
 * value from localStorage so personalized branches appear post-hydration with
 * no SSR/CSR mismatch. Also listens to the cross-tab `storage` event so signing
 * in/out in one tab updates the others. Swap this hook for a real session hook
 * when auth lands — callers shouldn't need to change.
 */
export function useMockUser() {
  const [user, setUser] = useState<MockUser | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setUser(getMockUser());
    setMounted(true);

    function onStorage(e: StorageEvent) {
      if (e.key === MOCK_USER_KEY) setUser(getMockUser());
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  function signIn(name?: string) {
    setUser(signInStore(name));
  }

  function signOut() {
    signOutStore();
    setUser(null);
  }

  return { user, mounted, signIn, signOut };
}
