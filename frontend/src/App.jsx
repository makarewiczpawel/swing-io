import { useState, useEffect } from "react";
import Header from "./components/Header";
import DashboardView from "./views/DashboardView";
import BacktestView from "./views/BacktestView";
import QuantView from "./views/QuantView";
import PatternsView from "./views/PatternsView";
import SignalsView from "./views/SignalsView";
import ChatView from "./views/ChatView";
import PerformanceView from "./views/PerformanceView";
import LoginView from "./views/LoginView";
import { getToken, getAuthStatus, logout as apiLogout } from "./api/client";

const TABS = [
  { id: "dashboard",   label: "Dashboard" },
  { id: "patterns",    label: "Formacje" },
  { id: "signals",     label: "Sygnały AI" },
  { id: "performance", label: "Performance" },
  { id: "chat",        label: "Chat" },
  { id: "backtest",    label: "Backtesting" },
  { id: "quant",       label: "Quant" },
];

export default function App() {
  const [tab, setTab]               = useState("dashboard");
  const [authRequired, setAuthReq]  = useState(null); // null = unknown
  const [isAuthed, setIsAuthed]     = useState(!!getToken());

  // Sprawdź czy backend wymaga logowania
  useEffect(() => {
    getAuthStatus()
      .then((s) => setAuthReq(s.auth_required))
      .catch(() => setAuthReq(false));
  }, []);

  // Nasłuchuj na 401 z API → wymuś re-login
  useEffect(() => {
    const handler = () => setIsAuthed(false);
    window.addEventListener("swing:auth-expired", handler);
    return () => window.removeEventListener("swing:auth-expired", handler);
  }, []);

  const handleLogout = () => {
    apiLogout();
    setIsAuthed(false);
  };

  // Loading state
  if (authRequired === null) {
    return (
      <div className="loading-state" style={{ height: "100vh" }}>
        <div className="spinner" /> Ładowanie…
      </div>
    );
  }

  // Login screen
  if (authRequired && !isAuthed) {
    return <LoginView onSuccess={() => setIsAuthed(true)} />;
  }

  return (
    <div className="app-layout">
      <Header onLogout={authRequired ? handleLogout : null} />

      <nav className="app-nav">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`nav-tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="app-content">
        {tab === "dashboard" && <DashboardView />}
        {tab === "chat" && (
          <div className="view-wrapper view-wrapper-chat">
            <ChatView />
          </div>
        )}
        {tab !== "dashboard" && tab !== "chat" && (
          <div className="view-wrapper">
            {tab === "patterns"    && <PatternsView />}
            {tab === "signals"     && <SignalsView />}
            {tab === "performance" && <PerformanceView />}
            {tab === "backtest"    && <BacktestView />}
            {tab === "quant"       && <QuantView />}
          </div>
        )}
      </div>
    </div>
  );
}
