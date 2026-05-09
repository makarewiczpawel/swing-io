const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

const TOKEN_KEY = "swing_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

function _authHeaders() {
  const t = getToken();
  return t ? { "Authorization": `Bearer ${t}` } : {};
}

function _handle401(response) {
  if (response.status === 401) {
    clearToken();
    // Force back to login screen
    window.dispatchEvent(new CustomEvent("swing:auth-expired"));
    throw new Error("Sesja wygasła — zaloguj się ponownie");
  }
}

async function fetchJSON(endpoint, params = {}) {
  const url = new URL(endpoint, window.location.origin);
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null) url.searchParams.set(key, val);
  });
  const response = await fetch(url, { headers: _authHeaders() });
  _handle401(response);
  if (!response.ok) throw new Error(`API Error: ${response.status} ${response.statusText}`);
  return response.json();
}

async function postJSON(endpoint, body = {}) {
  const response = await fetch(`${BASE_URL}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ..._authHeaders() },
    body: JSON.stringify(body),
  });
  _handle401(response);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `API Error: ${response.status}`);
  }
  return response.json();
}

export async function getAuthStatus() {
  const r = await fetch(`${BASE_URL}/auth/status`);
  if (!r.ok) throw new Error("Auth status check failed");
  return r.json();
}

export async function login(password) {
  const r = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `Login failed: ${r.status}`);
  }
  const { token } = await r.json();
  setToken(token);
  return token;
}

export function logout() {
  clearToken();
}

export const getCandles    = (interval = "1D", days = 365) => fetchJSON(`${BASE_URL}/candles`,          { interval, days });
export const getQuote      = ()                             => fetchJSON(`${BASE_URL}/quote`);
export const getMarketInfo = ()                             => fetchJSON(`${BASE_URL}/market-info`);
export const getIndicators = (interval = "1D", days = 365) => fetchJSON(`${BASE_URL}/indicators`,       { interval, days });
export const getRegime     = (interval = "1D")              => fetchJSON(`${BASE_URL}/regime/current`,   { interval });

export const getStrategies       = ()      => fetchJSON(`${BASE_URL}/backtest/strategies`);
export const runBacktest         = (body)  => postJSON("/backtest/run", body);
export const runWalkForward      = (body)  => postJSON("/backtest/walk-forward", body);
export const getBacktestResult   = (id)    => fetchJSON(`${BASE_URL}/backtest/${id}`);

export const getPatterns         = (interval = "1D", days = 180) => fetchJSON(`${BASE_URL}/patterns`, { interval, days });

export const runAnalysis         = (interval = "1D")  => postJSON(`/signals/analyze?interval=${interval}`, {});
export const getSignals          = ()                  => fetchJSON(`${BASE_URL}/signals`);
export const sendChat            = (message, history)  => postJSON("/chat", { message, history });

export const getQuantSnapshot    = ()              => fetchJSON(`${BASE_URL}/quant/current`);
export const getQuantRiskScore   = ()              => fetchJSON(`${BASE_URL}/quant/risk-score`);
export const getQuantVix         = (days = 252)    => fetchJSON(`${BASE_URL}/quant/vix`,          { days });
export const getQuantZScore      = (days = 252)    => fetchJSON(`${BASE_URL}/quant/zscore`,        { days });
export const getQuantCorrelations= (days = 252)    => fetchJSON(`${BASE_URL}/quant/correlations`,  { days });

export const getPerformance      = ()              => fetchJSON(`${BASE_URL}/performance`);
export const setCapital          = (amount)        => postJSON("/performance/capital", { amount });

export const getFeedbackStatus   = ()              => fetchJSON(`${BASE_URL}/feedback/status`);
export const setAlertsConfig     = (body)          => postJSON("/alerts/config", body);
export const sendTestAlert       = ()              => postJSON("/alerts/test", {});
