import { createContext, useContext } from "react";

// Shared authentication storage used by AuthProvider and dashboard components.
export const AuthContext = createContext(null);

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }

  return context;
}
