import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/useAuth.ts";

export function AppShell() {
  const { isAuthenticated, signOut, user } = useAuth();

  return (
    <div className="app-shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />

      <header className="site-header">
        <div className="site-header-inner">
          <Link className="brand-lockup" to="/">
            <span className="brand-mark">FD</span>
            <div>
              <strong>FastAPI Dispatch</strong>
              <span>Editorial frontend for your API workspace</span>
            </div>
          </Link>

          <nav className="site-nav">
            <NavLink className={({ isActive }) => (isActive ? "nav-link is-active" : "nav-link")} to="/">
              Home
            </NavLink>
            {isAuthenticated ? (
              <>
                <NavLink
                  className={({ isActive }) => (isActive ? "nav-link is-active" : "nav-link")}
                  to="/editor"
                >
                  Write
                </NavLink>
                <NavLink
                  className={({ isActive }) => (isActive ? "nav-link is-active" : "nav-link")}
                  to="/copilot"
                >
                  Copilot
                </NavLink>
                <NavLink
                  className={({ isActive }) => (isActive ? "nav-link is-active" : "nav-link")}
                  to="/profile"
                >
                  Profile
                </NavLink>
              </>
            ) : null}
          </nav>

          <div className="site-actions">
            <span className="status-chip">FastAPI v1</span>
            {isAuthenticated ? (
              <>
                <div className="user-chip">
                  <strong>{user?.full_name || user?.email}</strong>
                  <span>{user?.role}</span>
                </div>
                <button className="button button-secondary" onClick={signOut} type="button">
                  Sign out
                </button>
              </>
            ) : (
              <Link className="button button-primary" to="/auth">
                Sign in
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="page-shell">
        <Outlet />
      </main>
    </div>
  );
}
