import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth.ts";
import { getErrorMessage } from "../lib/format.ts";

type AuthMode = "login" | "register";

export function AuthPage() {
  const navigate = useNavigate();
  const { isAuthenticated, registerAndSignIn, signIn } = useAuth();
  const [mode, setMode] = useState<AuthMode>("login");
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerName, setRegisterName] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isAuthenticated) {
    return <Navigate replace to="/" />;
  }

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      await signIn(loginEmail, loginPassword);
      navigate("/");
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegister = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      await registerAndSignIn({
        email: registerEmail,
        password: registerPassword,
        full_name: registerName || undefined,
      });
      navigate("/");
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-layout">
      <section className="hero-card">
        <span className="eyebrow">Authentication bridge</span>
        <h1>Sign in to unlock articles, profiles, and the Copilot surface.</h1>
        <p className="hero-copy">
          The current backend protects article reads with bearer auth, so the frontend treats this
          screen as the gateway to the editorial workspace.
        </p>
        <div className="feature-grid">
          <div className="feature-card">
            <strong>Token-based session</strong>
            <p>Uses the existing login and refresh endpoints exposed by FastAPI.</p>
          </div>
          <div className="feature-card">
            <strong>Immediate write flow</strong>
            <p>Once authenticated, the editor and article detail routes are already active.</p>
          </div>
          <div className="feature-card">
            <strong>Dedicated Agent route</strong>
            <p>Copilot remains available after sign-in without colliding with article browsing.</p>
          </div>
        </div>
      </section>

      <section className="panel form-panel">
        <div className="tab-strip">
          <button
            className={`tab-button ${mode === "login" ? "is-active" : ""}`}
            onClick={() => setMode("login")}
            type="button"
          >
            Sign in
          </button>
          <button
            className={`tab-button ${mode === "register" ? "is-active" : ""}`}
            onClick={() => setMode("register")}
            type="button"
          >
            Register
          </button>
        </div>

        {errorMessage ? <p className="form-error">{errorMessage}</p> : null}

        {mode === "login" ? (
          <form className="form-grid" onSubmit={handleLogin}>
            <label className="input-shell">
              <span>Email</span>
              <input
                autoComplete="email"
                onChange={(event) => setLoginEmail(event.target.value)}
                placeholder="you@example.com"
                required
                type="email"
                value={loginEmail}
              />
            </label>

            <label className="input-shell">
              <span>Password</span>
              <input
                autoComplete="current-password"
                onChange={(event) => setLoginPassword(event.target.value)}
                placeholder="Enter your password"
                required
                type="password"
                value={loginPassword}
              />
            </label>

            <button className="button button-primary" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Signing in..." : "Sign in"}
            </button>
          </form>
        ) : (
          <form className="form-grid" onSubmit={handleRegister}>
            <label className="input-shell">
              <span>Full name</span>
              <input
                autoComplete="name"
                onChange={(event) => setRegisterName(event.target.value)}
                placeholder="Editorial owner"
                type="text"
                value={registerName}
              />
            </label>

            <label className="input-shell">
              <span>Email</span>
              <input
                autoComplete="email"
                onChange={(event) => setRegisterEmail(event.target.value)}
                placeholder="new@reader.com"
                required
                type="email"
                value={registerEmail}
              />
            </label>

            <label className="input-shell">
              <span>Password</span>
              <input
                autoComplete="new-password"
                onChange={(event) => setRegisterPassword(event.target.value)}
                placeholder="Create a password"
                required
                type="password"
                value={registerPassword}
              />
            </label>

            <button className="button button-primary" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Creating account..." : "Create account"}
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
