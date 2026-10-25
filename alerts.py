import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
import logging

from database import record_alert

logger = logging.getLogger("website_health_monitor.alerts")


def get_smtp_config() -> Dict[str, Any]:
    """Retrieve SMTP settings from environment variables."""
    host = os.environ.get("SMTP_HOST", "").strip()
    port_str = os.environ.get("SMTP_PORT", "587").strip()
    try:
        port = int(port_str)
    except ValueError:
        port = 587

    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "").strip()
    from_email = os.environ.get("ALERT_FROM_EMAIL", "").strip() or user
    to_email = os.environ.get("ALERT_TO_EMAIL", "").strip()
    use_tls = os.environ.get("SMTP_USE_TLS", "True").strip().lower() in ("true", "1", "yes")
    use_ssl = os.environ.get("SMTP_USE_SSL", "False").strip().lower() in ("true", "1", "yes")

    is_configured = bool(host and to_email and (user or not password))

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_email": from_email,
        "to_email": to_email,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
        "is_configured": is_configured,
    }


def is_smtp_configured() -> bool:
    """Return True if required SMTP settings are present."""
    return get_smtp_config()["is_configured"]


def send_email_alert(
    subject: str,
    text_content: str,
    html_content: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Attempt to send an email via SMTP.
    Returns (success: bool, error_message: Optional[str]).
    """
    config = get_smtp_config()

    if not config["is_configured"]:
        return False, "SMTP is not configured in environment variables."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["from_email"]
    msg["To"] = config["to_email"]
    msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    part1 = MIMEText(text_content, "plain")
    msg.attach(part1)

    if html_content:
        part2 = MIMEText(html_content, "html")
        msg.attach(part2)

    try:
        if config["use_ssl"]:
            server = smtplib.SMTP_SSL(config["host"], config["port"], timeout=10)
        else:
            server = smtplib.SMTP(config["host"], config["port"], timeout=10)

        with server:
            if config["use_tls"] and not config["use_ssl"]:
                server.ehlo()
                server.starttls()
                server.ehlo()

            if config["user"] and config["password"]:
                server.login(config["user"], config["password"])

            server.sendmail(config["from_email"], [config["to_email"]], msg.as_string())

        logger.info(f"Email alert sent successfully to {config['to_email']}: {subject}")
        return True, None
    except Exception as exc:
        err_msg = f"Failed to send email alert: {str(exc)}"
        logger.error(err_msg)
        return False, err_msg


def trigger_alert(
    website_id: int,
    website_name: str,
    website_url: str,
    alert_type: str,
    status_code: Optional[int],
    error_message: Optional[str],
    response_time_ms: Optional[float] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate an alert for a website transition (downtime or recovery),
    dispatch an email if SMTP is configured, and record the event in SQLite.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if alert_type == "downtime":
        subject = f"[ALERT] DOWN: {website_name} ({website_url}) is unreachable"
        reason = error_message or (f"HTTP {status_code}" if status_code else "Unknown connection error")
        text_body = (
            f"WEBSITE DOWNTIME ALERT\n\n"
            f"Website: {website_name}\n"
            f"URL: {website_url}\n"
            f"Status: OFFLINE\n"
            f"Failure Reason: {reason}\n"
            f"Detected At: {now_utc}\n\n"
            f"The health monitoring service will notify you as soon as this website recovers.\n"
        )
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #1e293b; background: #f8fafc; padding: 20px;">
          <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
            <div style="background: #ef4444; color: #ffffff; padding: 18px 24px; font-weight: bold; font-size: 18px;">
              ⚠️ Website Downtime Alert
            </div>
            <div style="padding: 24px;">
              <p>The health monitor detected that your website is currently <strong>OFFLINE</strong>.</p>
              <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <tr><td style="padding: 8px 0; color: #64748b;">Website Name:</td><td style="font-weight: 600;">{website_name}</td></tr>
                <tr><td style="padding: 8px 0; color: #64748b;">Target URL:</td><td><a href="{website_url}" style="color: #0284c7;">{website_url}</a></td></tr>
                <tr><td style="padding: 8px 0; color: #64748b;">Status:</td><td><span style="color: #ef4444; font-weight: bold;">OFFLINE</span></td></tr>
                <tr><td style="padding: 8px 0; color: #64748b;">Failure Reason:</td><td style="color: #ef4444;">{reason}</td></tr>
                <tr><td style="padding: 8px 0; color: #64748b;">Timestamp:</td><td>{now_utc}</td></tr>
              </table>
            </div>
            <div style="background: #f1f5f9; padding: 12px 24px; font-size: 12px; color: #64748b; text-align: center;">
              Website Health Monitor with Auto-Alerts
            </div>
          </div>
        </body>
        </html>
        """
    else:  # recovery
        subject = f"[RESOLVED] UP: {website_name} ({website_url}) has recovered"
        rt_info = f"{response_time_ms} ms" if response_time_ms is not None else "N/A"
        text_body = (
            f"WEBSITE RECOVERY ALERT\n\n"
            f"Website: {website_name}\n"
            f"URL: {website_url}\n"
            f"Status: ONLINE\n"
            f"HTTP Status Code: {status_code or 'OK'}\n"
            f"Response Time: {rt_info}\n"
            f"Recovered At: {now_utc}\n\n"
            f"Your website is responding normally.\n"
        )
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #1e293b; background: #f8fafc; padding: 20px;">
          <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
            <div style="background: #10b981; color: #ffffff; padding: 18px 24px; font-weight: bold; font-size: 18px;">
              ✅ Website Recovery Alert
            </div>
            <div style="padding: 24px;">
              <p>Good news! Your website is back <strong>ONLINE</strong> and responding normally.</p>
              <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <tr><td style="padding: 8px 0; color: #64748b;">Website Name:</td><td style="font-weight: 600;">{website_name}</td></tr>
                <tr><td style="padding: 8px 0; color: #64748b;">Target URL:</td><td><a href="{website_url}" style="color: #0284c7;">{website_url}</a></td></tr>
                <tr><td style="padding: 8px 0; color: #64748b;">Status:</td><td><span style="color: #10b981; font-weight: bold;">ONLINE</span></td></tr>
                <tr><td style="padding: 8px 0; color: #64748b;">HTTP Code:</td><td>{status_code or 200}</td></tr>
                <tr><td style="padding: 8px 0; color: #64748b;">Response Time:</td><td>{rt_info}</td></tr>
                <tr><td style="padding: 8px 0; color: #64748b;">Timestamp:</td><td>{now_utc}</td></tr>
              </table>
            </div>
            <div style="background: #f1f5f9; padding: 12px 24px; font-size: 12px; color: #64748b; text-align: center;">
              Website Health Monitor with Auto-Alerts
            </div>
          </div>
        </body>
        </html>
        """

    smtp_cfg = get_smtp_config()
    if smtp_cfg["is_configured"]:
        success, err = send_email_alert(subject, text_body, html_body)
        delivery_status = "sent" if success else "failed"
        delivery_error = err
    else:
        delivery_status = "skipped_no_smtp"
        delivery_error = "SMTP credentials not configured"

    alert_id = record_alert(
        website_id=website_id,
        alert_type=alert_type,
        status_code=status_code,
        error_message=error_message,
        delivery_status=delivery_status,
        delivery_error=delivery_error,
        db_path=db_path,
    )

    return {
        "alert_id": alert_id,
        "website_id": website_id,
        "alert_type": alert_type,
        "delivery_status": delivery_status,
        "delivery_error": delivery_error,
    }
