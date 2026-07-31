import React, { useEffect, useRef } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

export default function ProtectedRoute({ children, roles }) {
  const { user, ready } = useAuth();
  const location = useLocation();
  const loggedRef = useRef("");

  const denied = ready && user && roles && !roles.includes(user.role);

  useEffect(() => {
    if (!denied) return;
    // Log once per unique path to avoid duplicate audit entries on re-render.
    if (loggedRef.current === location.pathname) return;
    loggedRef.current = location.pathname;
    api
      .post("/audit/access-denied", { path: location.pathname, required_roles: roles })
      .catch(() => {});
  }, [denied, location.pathname, roles]);

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-sm text-muted-foreground mono">Authenticating…</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (roles && !roles.includes(user.role))
    return (
      <div className="p-10">
        <h1 className="text-2xl font-display font-bold">Access denied</h1>
        <p className="text-muted-foreground mt-2">
          Your role ({user.role}) cannot access this page.
        </p>
      </div>
    );
  return children;
}
