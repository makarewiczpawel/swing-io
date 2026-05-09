import { useQuote } from "../hooks/useMarketData";

/**
 * Header z logo i bieżącą ceną S&P 500.
 */
export default function Header({ onLogout = null }) {
  const { quote, loading } = useQuote(60000);

  const isUp = quote && quote.change >= 0;
  const changeDir = isUp ? "up" : "down";
  const changeSign = isUp ? "+" : "";

  return (
    <header className="app-header">
      <div className="app-logo">
        <div className="app-logo-icon">S</div>
        <div className="app-logo-text">
          swing<span>.io</span>
        </div>
      </div>

      {quote && !loading && (
        <div className="quote-bar">
          <span className="quote-price">
            {quote.price.toLocaleString("en-US", {
              minimumFractionDigits: 2,
            })}
          </span>

          <span className={`quote-change ${changeDir}`}>
            {changeSign}
            {quote.change.toFixed(2)} ({changeSign}
            {quote.change_pct.toFixed(2)}%)
          </span>

          <div className="quote-detail">
            <span className="quote-detail-label">Open</span>
            <span className="quote-detail-value">
              {quote.open.toLocaleString("en-US", {
                minimumFractionDigits: 2,
              })}
            </span>
          </div>

          <div className="quote-detail">
            <span className="quote-detail-label">High</span>
            <span className="quote-detail-value">
              {quote.high.toLocaleString("en-US", {
                minimumFractionDigits: 2,
              })}
            </span>
          </div>

          <div className="quote-detail">
            <span className="quote-detail-label">Low</span>
            <span className="quote-detail-value">
              {quote.low.toLocaleString("en-US", {
                minimumFractionDigits: 2,
              })}
            </span>
          </div>

          <div className="quote-detail">
            <span className="quote-detail-label">Prev Close</span>
            <span className="quote-detail-value">
              {quote.prev_close.toLocaleString("en-US", {
                minimumFractionDigits: 2,
              })}
            </span>
          </div>
        </div>
      )}

      {loading && (
        <div className="quote-bar">
          <span className="quote-price" style={{ opacity: 0.3 }}>
            Loading...
          </span>
        </div>
      )}

      {onLogout && (
        <button className="header-logout-btn" onClick={onLogout} title="Wyloguj">
          Wyloguj
        </button>
      )}
    </header>
  );
}
