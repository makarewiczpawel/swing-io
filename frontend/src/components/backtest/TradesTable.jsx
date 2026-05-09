import { useState } from "react";

const PAGE = 15;

export default function TradesTable({ trades, title }) {
  const [page, setPage] = useState(0);
  if (!trades?.length) return <p className="text-muted" style={{padding:"8px 0"}}>Brak transakcji</p>;

  const pages = Math.ceil(trades.length / PAGE);
  const slice = trades.slice(page * PAGE, page * PAGE + PAGE);

  return (
    <div className="bt-trades">
      <h4 className="bt-section-label">{title} ({trades.length} transakcji)</h4>
      <table className="bt-table">
        <thead>
          <tr>
            <th>Wejście</th><th>Wyjście</th>
            <th>Cena wejścia</th><th>Cena wyjścia</th>
            <th>P&L %</th><th>P&L $</th>
            <th>Świece</th><th>Powód</th>
          </tr>
        </thead>
        <tbody>
          {slice.map((t, i) => (
            <tr key={i}>
              <td>{t.entry_date}</td>
              <td>{t.exit_date}</td>
              <td>{t.entry_price.toLocaleString()}</td>
              <td>{t.exit_price.toLocaleString()}</td>
              <td className={t.pnl_pct >= 0 ? "positive" : "negative"}>
                {t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct.toFixed(2)}%
              </td>
              <td className={t.pnl_amount >= 0 ? "positive" : "negative"}>
                {t.pnl_amount >= 0 ? "+" : ""}{t.pnl_amount.toLocaleString("pl-PL", { maximumFractionDigits: 0 })}
              </td>
              <td>{t.bars_held}</td>
              <td className="text-muted">{t.exit_reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {pages > 1 && (
        <div className="bt-pagination">
          <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>←</button>
          <span>{page + 1} / {pages}</span>
          <button onClick={() => setPage((p) => Math.min(pages - 1, p + 1))} disabled={page === pages - 1}>→</button>
        </div>
      )}
    </div>
  );
}
