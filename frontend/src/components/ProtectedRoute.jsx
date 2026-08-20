import {
  Navigate,
  useLocation,
} from "react-router-dom";

import { useAuth } from "../context/authContextValue";

function hasPermission(membership, requiredPermission) {
  if (!requiredPermission || membership?.role === "owner") {
    return true;
  }

  const permissions = membership?.permissions ?? [];
  const resource = requiredPermission.split(":", 1)[0];

  return (
    permissions.includes("*")
    || permissions.includes(requiredPermission)
    || permissions.includes(`${resource}:*`)
  );
}

function ProtectedRoute({
  children,
  requireSellerProfile = true,
  permission = null,
}) {
  const {
    isAuthenticated,
    isAuthLoading,
    sellerProfile,
    membership,
  } = useAuth();

  const location = useLocation();

  // Wait until Firebase finishes checking the saved login session.
  if (isAuthLoading) {
    return null;
  }

  // Send logged-out users to the login page.
  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: location.pathname,
        }}
      />
    );
  }

  // Google users and older accounts complete their business profile once.
  if (requireSellerProfile && !sellerProfile) {
    return <Navigate to="/setup-business" replace />;
  }

  // Keep staff away from dashboard pages their assigned role cannot access.
  if (permission && !hasPermission(membership, permission)) {
    return <Navigate to="/" replace />;
  }

  // Logged-in users can view the protected page.
  return children;
}

export default ProtectedRoute;
