import { startTransition, useEffect, useState } from "react";
import type { PropsWithChildren } from "react";
import { AuthContext } from "./context.ts";
import { authApi, usersApi } from "../lib/api.ts";
import { clearStoredAuth, getStoredAuth, setStoredAuth } from "../lib/storage.ts";
import type { RegisterPayload, User } from "../types.ts";

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<User | null>(null);
  const [isRestoring, setIsRestoring] = useState(true);

  useEffect(() => {
    const restoreSession = async () => {
      if (!getStoredAuth()) {
        setIsRestoring(false);
        return;
      }

      try {
        const currentUser = await usersApi.getCurrentUser();
        startTransition(() => {
          setUser(currentUser);
        });
      } catch {
        clearStoredAuth();
        startTransition(() => {
          setUser(null);
        });
      } finally {
        setIsRestoring(false);
      }
    };

    void restoreSession();
  }, []);

  const refreshCurrentUser = async () => {
    const currentUser = await usersApi.getCurrentUser();
    startTransition(() => {
      setUser(currentUser);
    });
  };

  const signIn = async (email: string, password: string) => {
    const tokens = await authApi.login(email, password);
    setStoredAuth({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
    });
    await refreshCurrentUser();
  };

  const registerAndSignIn = async (payload: RegisterPayload) => {
    await usersApi.register(payload);
    await signIn(payload.email, payload.password);
  };

  const signOut = () => {
    clearStoredAuth();
    startTransition(() => {
      setUser(null);
    });
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isRestoring,
        signIn,
        registerAndSignIn,
        signOut,
        refreshCurrentUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
