import { useState } from "react";
import { login } from "../api/client";

export default function LoginView({ onSuccess }) {
  const [password, setPassword] = useState("");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  const submit = async (e) => {
    e.preventDefault();
    if (!password.trim() || loading) return;
    setLoading(true);
    setError("");
    try {
      await login(password);
      onSuccess();
    } catch (err) {
      setError(err.message || "Błąd logowania");
      setPassword("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="login-card">
        <div className="login-header">
          <div className="app-logo-icon">SW</div>
          <h1 className="login-title">swing<span>.io</span></h1>
        </div>
        <p className="login-subtitle">Analiza S&amp;P 500 — wymagane logowanie</p>
        <form onSubmit={submit} className="login-form">
          <input
            type="password"
            placeholder="Hasło"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="login-input"
            autoFocus
            autoComplete="current-password"
            disabled={loading}
          />
          {error && <div className="login-error">{error}</div>}
          <button type="submit" className="login-btn" disabled={loading || !password.trim()}>
            {loading ? "Logowanie…" : "Zaloguj"}
          </button>
        </form>
      </div>
    </div>
  );
}
