import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/useAuth.ts";
import { StatusView } from "./StatusView.tsx";

export function RequireAuth() {
  const { isAuthenticated, isRestoring } = useAuth();
  const location = useLocation();

  if (isRestoring) {
    return (
      <StatusView
        title="Restoring your workspace"
        detail="Checking your access token and reconnecting to the backend."
      />
    );
  }

  if (!isAuthenticated) {
    return <Navigate replace state={{ from: location }} to="/auth" />;
  }

  return <Outlet />;
}
