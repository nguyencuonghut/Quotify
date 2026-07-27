from __future__ import annotations

import asyncio
import logging
import smtplib
import zoneinfo
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _format_size(self, size_bytes: int | None) -> str:
        if size_bytes is None:
            return "N/A"
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    def _send_raw_email(self, recipient: str, subject: str, html_content: str) -> None:
        smtp_host = self.settings.smtp_host
        smtp_port = self.settings.smtp_port
        smtp_user = self.settings.smtp_user
        smtp_password = self.settings.smtp_password
        smtp_secure = self.settings.smtp_secure
        from_email = self.settings.smtp_from_email

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = recipient

        msg.attach(MIMEText(html_content, "html"))

        # Send email via SMTP
        logger.info(f"Connecting to SMTP server at {smtp_host}:{smtp_port}")
        # Standard SMTP connection
        server: smtplib.SMTP | smtplib.SMTP_SSL
        if smtp_secure:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            # Try STARTTLS if available
            try:
                server.ehlo()
                if server.has_extn("STARTTLS"):
                    server.starttls()
                    server.ehlo()
            except Exception:  # nosec B110
                # Fallback to plain connection if STARTTLS fails (e.g. locally in Mailpit)
                pass

        try:
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(from_email, [recipient], msg.as_string())
            logger.info(f"Email sent successfully to {recipient}")
        finally:
            server.quit()

    async def send_backup_notification(
        self,
        status: str,  # success / failed
        backup_type: str,  # manual / scheduled
        filename: str | None,
        file_size_bytes: int | None,
        started_at: datetime,
        completed_at: datetime,
        error_message: str | None = None,
    ) -> None:
        tz = zoneinfo.ZoneInfo(self.settings.app_timezone)

        # Convert datetimes to local timezone for user-facing email display
        local_started = started_at
        if local_started.tzinfo is None:
            local_started = local_started.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        local_started = local_started.astimezone(tz)

        local_completed = completed_at
        if local_completed.tzinfo is None:
            local_completed = local_completed.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        local_completed = local_completed.astimezone(tz)

        recipient = self.settings.admin_email_for_backups
        subject_status = "THÀNH CÔNG" if status == "success" else "THẤT BẠI"
        subject = (
            f"[Backup System] - Postgres Backup - {subject_status} - "
            f"{local_completed.strftime('%d/%m/%Y %H:%M:%S')}"
        )

        duration = int((completed_at - started_at).total_seconds())
        size_str = self._format_size(file_size_bytes)

        # Build premium HTML email with Outfit/Inter typography and harmonious layout
        status_color = "#10B981" if status == "success" else "#EF4444"
        status_text = "Thành công" if status == "success" else "Thất bại"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{subject}</title>
            <style>
                body {{
                    font-family: 'Outfit', 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #f8fafc;
                    margin: 0;
                    padding: 0;
                    color: #1e293b;
                }}
                .container {{
                    max-width: 600px;
                    margin: 40px auto;
                    background: #ffffff;
                    border-radius: 12px;
                    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05),
                                0 4px 6px -2px rgba(0, 0, 0, 0.05);
                    overflow: hidden;
                    border: 1px solid #e2e8f0;
                }}
                .header {{
                    background: linear-gradient(135deg, #1e1b4b, #312e81);
                    padding: 30px 40px;
                    text-align: center;
                }}
                .header h1 {{
                    color: #ffffff;
                    margin: 0;
                    font-size: 22px;
                    font-weight: 600;
                    letter-spacing: 0.5px;
                }}
                .content {{
                    padding: 40px;
                }}
                .status-badge {{
                    display: inline-block;
                    padding: 8px 16px;
                    background-color: {status_color};
                    color: #ffffff;
                    font-weight: 600;
                    border-radius: 9999px;
                    font-size: 14px;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    margin-bottom: 24px;
                }}
                .details-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                }}
                .details-table td {{
                    padding: 12px 0;
                    border-bottom: 1px solid #f1f5f9;
                    font-size: 15px;
                }}
                .details-table td.label {{
                    color: #64748b;
                    font-weight: 500;
                    width: 35%;
                }}
                .details-table td.value {{
                    color: #0f172a;
                    font-weight: 600;
                    word-break: break-all;
                }}
                .error-card {{
                    background-color: #fef2f2;
                    border-left: 4px solid #ef4444;
                    padding: 16px 20px;
                    border-radius: 4px;
                    margin-top: 24px;
                }}
                .error-card h3 {{
                    margin: 0 0 8px 0;
                    color: #991b1b;
                    font-size: 15px;
                }}
                .error-card p {{
                    margin: 0;
                    color: #7f1d1d;
                    font-family: monospace;
                    font-size: 13px;
                    white-space: pre-wrap;
                }}
                .footer {{
                    background-color: #f8fafc;
                    padding: 20px 40px;
                    text-align: center;
                    font-size: 13px;
                    color: #94a3b8;
                    border-top: 1px solid #e2e8f0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>HỆ THỐNG SAO LƯU DỰ PHÒNG</h1>
                </div>
                <div class="content">
                    <div style="text-align: center;">
                        <span class="status-badge">{status_text}</span>
                    </div>
                    <table class="details-table">
                        <tr>
                            <td class="label">Loại sao lưu</td>
                            <td class="value">{backup_type.upper()}</td>
                        </tr>
                        <tr>
                            <td class="label">Trạng thái</td>
                            <td class="value" style="color: {status_color};">
                                {status_text.upper()}
                            </td>
                        </tr>
                        {
            f'<tr><td class="label">Tên tệp</td><td class="value">{filename}</td></tr>'
            if filename
            else ""
        }
                        {
            f'<tr><td class="label">Kích thước</td><td class="value">{size_str}</td></tr>'
            if file_size_bytes
            else ""
        }
                        <tr>
                            <td class="label">Thời gian bắt đầu</td>
                            <td class="value">
                                {local_started.strftime("%d/%m/%Y %H:%M:%S")} (GMT+7)
                            </td>
                        </tr>
                        <tr>
                            <td class="label">Thời gian hoàn tất</td>
                            <td class="value">
                                {local_completed.strftime("%d/%m/%Y %H:%M:%S")} (GMT+7)
                            </td>
                        </tr>
                        <tr>
                            <td class="label">Thời gian chạy</td>
                            <td class="value">{duration} giây</td>
                        </tr>
                    </table>
                    
                    {
            f'''
                    <div class="error-card">
                        <h3>Chi tiết lỗi:</h3>
                        <p>{error_message}</p>
                    </div>
                    '''
            if error_message
            else ""
        }
                </div>
                <div class="footer">
                    Email tự động từ hệ thống quản trị {self.settings.app_name}.<br>
                    Timezone hệ thống: {self.settings.app_timezone}
                </div>
            </div>
        </body>
        </html>
        """

        try:
            await asyncio.to_thread(self._send_raw_email, recipient, subject, html_content)
        except Exception:
            logger.exception(f"Failed to send backup status notification email to {recipient}")
