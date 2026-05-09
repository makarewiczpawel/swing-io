import { useState } from "react";
import Header from "./components/Header";
import DashboardView from "./views/DashboardView";
import BacktestView from "./views/BacktestView";
import QuantView from "./views/QuantView";
import PatternsView from "./views/PatternsView";
import SignalsView from "./views/SignalsView";
import ChatView from "./views/ChatView";
import PerformanceView from "./views/PerformanceView";

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
  const [tab, setTab] = useState("dashboard");

  return (
    <div className="app-layout">
      <Header />

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
