"""
Email Service — Faza 6.
Wysyła alerty przy nowym sygnale BUY/SELL.
"""

import logging
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SIGNAL_EMOJI = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}


def _fmt(val, suffix: str = "", precision: int = 2) -> str:
    """Format float z fallbackiem '—' dla None."""
    if val is None:
        return "—"
    try:
        return f"{float(val):.{precision}f}{suffix}"
    except (TypeError, ValueError):
        return "—"


def send_signal_alert(result: dict, in_background: bool = True) -> bool:
    """
    Wyślij email z nowym sygnałem.
    in_background=True: SMTP w wątku — nie blokuje analizy. Zwraca True jeśli zakolejkowano.
    in_background=False: synchronicznie. Zwraca True jeśli wysłano.
    """
    settings = get_settings()
    if not settings.alerts_enabled:
        return False
    if not all([settings.smtp_host, settings.smtp_user, settings.smtp_password, settings.alert_recipient]):
        logger.warning("Email alerts: brak konfiguracji SMTP — pomijam")
        return False

    signal = result.get("signal", "HOLD")
    if signal == "HOLD":
        return False

    if in_background:
        threading.Thread(target=_send_sync, args=(result,), daemon=True).start()
        return True
    return _send_sync(result)


def _send_sync(result: dict, raise_on_error: bool = False) -> bool:
    settings = get_settings()
    signal = result.get("signal", "HOLD")
    try:
        subject = f"{SIGNAL_EMOJI.get(signal, '')} swing.io — Sygnał {signal} S&P 500"
        body = _build_body(result)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = settings.smtp_user
        msg["To"]      = settings.alert_recipient
        msg.attach(MIMEText(body, "html", "utf-8"))

        # Hasło aplikacji Gmail może mieć spacje — usuń żeby ujednolicić
        smtp_pwd = (settings.smtp_password or "").replace(" ", "")

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, smtp_pwd)
            server.sendmail(settings.smtp_user, settings.alert_recipient, msg.as_string())

        logger.info(f"Alert email wysłany: {signal} → {settings.alert_recipient}")
        return True

    except Exception as e:
        logger.error(f"Błąd wysyłania emaila: {type(e).__name__}: {e}")
        if raise_on_error:
            raise
        return False


def _build_body(result: dict) -> str:
    signal     = result.get("signal", "")
    confidence = result.get("confidence", 0)
    entry      = result.get("entry_price")
    sl         = result.get("stop_loss")
    tp         = result.get("take_profit")
    rr         = result.get("rr_ratio")
    size       = result.get("position_size_pct")
    reasoning  = result.get("reasoning", "")
    factors    = result.get("key_factors", [])
    ts         = result.get("timestamp", datetime.now().isoformat())
    approved   = result.get("risk_approved", True)

    color = {"BUY": "#10b981", "SELL": "#ef4444", "HOLD": "#f59e0b"}.get(signal, "#94a3b8")

    factors_html = "".join(
        f'<li style="margin:4px 0;color:#94a3b8">{f}</li>' for f in factors
    )

    levels_html = ""
    if entry:
        levels_html = f"""
        <table style="width:100%;border-collapse:collapse;margin:12px 0">
          <tr>
            <td style="padding:6px 12px;border:1px solid #1e293b;color:#94a3b8;font-size:12px">Entry</td>
            <td style="padding:6px 12px;border:1px solid #1e293b;font-family:monospace">{_fmt(entry)}</td>
          </tr>
          <tr>
            <td style="padding:6px 12px;border:1px solid #1e293b;color:#94a3b8;font-size:12px">Stop Loss</td>
            <td style="padding:6px 12px;border:1px solid #1e293b;color:#ef4444;font-family:monospace">{_fmt(sl)}</td>
          </tr>
          <tr>
            <td style="padding:6px 12px;border:1px solid #1e293b;color:#94a3b8;font-size:12px">Take Profit</td>
            <td style="padding:6px 12px;border:1px solid #1e293b;color:#10b981;font-family:monospace">{_fmt(tp)}</td>
          </tr>
          <tr>
            <td style="padding:6px 12px;border:1px solid #1e293b;color:#94a3b8;font-size:12px">R/R</td>
            <td style="padding:6px 12px;border:1px solid #1e293b;font-family:monospace">{_fmt(rr)}</td>
          </tr>
          <tr>
            <td style="padding:6px 12px;border:1px solid #1e293b;color:#94a3b8;font-size:12px">Wielkość</td>
            <td style="padding:6px 12px;border:1px solid #1e293b;font-family:monospace">{_fmt(size, '%', 1)}</td>
          </tr>
        </table>
        """

    risk_note = "" if approved else '<p style="color:#ef4444;font-size:12px">⚠ Risk Manager odrzucił sygnał</p>'
    factors_block = (
        '<h3 style="font-size:13px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em">Kluczowe czynniki</h3>'
        f'<ul style="padding-left:20px">{factors_html}</ul>'
    ) if factors else ""

    return f"""
    <html><body style="background:#0a0e17;color:#e2e8f0;font-family:sans-serif;padding:24px;max-width:600px">
      <h1 style="font-size:28px;margin:0 0 4px">
        <span style="color:{color}">{signal}</span>
        <span style="font-size:14px;color:#64748b;font-weight:normal;margin-left:12px">S&P 500</span>
      </h1>
      <p style="color:#64748b;font-size:12px;margin:0 0 20px">{ts[:19].replace("T"," ")}</p>

      <div style="background:#1e293b;border-radius:8px;padding:8px 16px;display:inline-block;margin-bottom:16px">
        <span style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:0.1em">Pewność</span>
        <span style="color:{color};font-size:20px;font-weight:700;margin-left:12px">{confidence}%</span>
      </div>

      {risk_note}
      {levels_html}

      <h3 style="font-size:13px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em">Uzasadnienie</h3>
      <p style="line-height:1.6;color:#cbd5e1">{reasoning}</p>

      {factors_block}

      <hr style="border:1px solid #1e293b;margin:24px 0">
      <p style="color:#475569;font-size:11px">swing.io — automatyczny alert tradingowy</p>
    </body></html>
    """
