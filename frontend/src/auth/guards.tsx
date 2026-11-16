import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import type { Role } from "../api/types";
import { Spinner } from "../components/ui";
import { HOME_BY_ROLE, useAuth } from "./AuthContext";

/** Client-side route guard. The backend enforces the same rules on every endpoint;
 * this only keeps users out of screens they cannot use. */
export function RequireAuth({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user, ready } = useAuth();
  const location = useLocation();
  if (!ready) return <Spinner label="Checking your session…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (roles && !roles.includes(user.role)) return <Navigate to={HOME_BY_ROLE[user.role]} replace />;
  return <>{children}</>;
}

export function HomeRedirect() {
  const { user, ready } = useAuth();
  if (!ready) return <Spinner />;
  return <Navigate to={user ? HOME_BY_ROLE[user.role] : "/login"} replace />;
}
