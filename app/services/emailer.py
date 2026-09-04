import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.config import settings


def _send_sync(to: str, subject: str, html: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_email
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(settings.smtp_email, settings.smtp_password)
        server.sendmail(settings.smtp_email, to, msg.as_string())


async def send_job_alert_email(alerts: list[dict], batch_index: int = 1, batch_total: int = 1) -> None:
    if not alerts:
        return

    count = len(alerts)
    subject = f"JobScout: {count} new job{'s' if count > 1 else ''} found"
    if batch_total > 1:
        subject += f" (part {batch_index}/{batch_total})"

    rows = "".join(
        f"""
        <tr style="border-bottom:1px solid #eee">
            <td style="padding:12px 8px">
                <div style="font-weight:600;color:#1a1a1a">{a["job_title"]}</div>
                <div style="font-size:13px;color:#555;margin-top:2px">{a["company"]}</div>
            </td>
            <td style="padding:12px 8px;color:#555;font-size:13px">{a.get("location", "India")}</td>
            <td style="padding:12px 8px;text-align:center;font-size:13px;color:#555">{a.get("company_rating") or "N/A"}</td>
            <td style="padding:12px 8px;text-align:center;font-size:13px;color:#888">{a.get("posted_at") or "—"}</td>
            <td style="padding:12px 8px;text-align:center;font-size:13px;font-weight:600;color:#1a73e8">{a.get("match_score", "—")}</td>
            <td style="padding:12px 8px;text-align:center">
                <a href="{a['job_url']}" style="background:#1a73e8;color:#fff;padding:6px 14px;border-radius:4px;text-decoration:none;font-size:13px">Apply</a>
            </td>
        </tr>"""
        for a in alerts
    )

    html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#222;max-width:900px;margin:0 auto;padding:24px">

    <div style="border-bottom:2px solid #1a73e8;padding-bottom:12px;margin-bottom:24px">
        <h2 style="color:#1a73e8;margin:0">JobScout</h2>
        <p style="color:#555;margin:4px 0 0">{count} new job{'s' if count > 1 else ''} found</p>
    </div>

    <table style="width:100%;border-collapse:collapse">
        <thead>
            <tr style="background:#f8f9fa;text-align:left">
                <th style="padding:10px 8px;font-size:13px;color:#555;font-weight:600">Job</th>
                <th style="padding:10px 8px;font-size:13px;color:#555;font-weight:600">Location</th>
                <th style="padding:10px 8px;font-size:13px;color:#555;font-weight:600;text-align:center">Rating</th>
                <th style="padding:10px 8px;font-size:13px;color:#555;font-weight:600;text-align:center">Posted</th>
                <th style="padding:10px 8px;font-size:13px;color:#555;font-weight:600;text-align:center">Match</th>
                <th style="padding:10px 8px;font-size:13px;color:#555;font-weight:600;text-align:center">Link</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>

    <p style="color:#aaa;font-size:11px;margin-top:32px;border-top:1px solid #eee;padding-top:12px">
        Sent by JobScout
    </p>

    </body></html>
    """

    await asyncio.to_thread(_send_sync, settings.alert_email, subject, html)


async def send_digest(alerts: list[dict]) -> None:
    """Send the daily digest using the same alert template."""
    await send_job_alert_email(alerts)
