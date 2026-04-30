import { createContext } from "react";
import type { RegisterPayload, User } from "../types.ts";

export type AuthContextValue = {
  user: User | null;
  isAuthenticated: boolean;
  isRestoring: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  registerAndSignIn: (payload: RegisterPayload) => Promise<void>;
  signOut: () => void;
  refreshCurrentUser: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);
