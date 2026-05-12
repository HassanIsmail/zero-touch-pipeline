import base64
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

import markdown as md

import config
from exceptions import PipelineError

log = logging.getLogger("pipeline")


def send(issue_key: str, qa_status: str, out_dir: str) -> None:
    report_path = os.path.join(out_dir, "bug-report.md")
    if not os.path.exists(report_path):
        raise PipelineError("bug-report.md not found", stage="email-reporter")

    with open(report_path) as f:
        raw_md = f.read()

    subject = f"QA Report — {issue_key} — {qa_status}"
    html_body = _md_to_html(raw_md)

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_FROM
    msg["To"] = config.EMAIL_TO
    msg.attach(MIMEText(html_body, "html"))

    for attachment in _collect_screenshots(out_dir):
        msg.attach(attachment)

    log.info("[%s] Sending QA email to %s…", issue_key, config.EMAIL_TO)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.EMAIL_FROM, config.EMAIL_TO, msg.as_string())
        log.info("[%s] Email sent successfully.", issue_key)
    except Exception as e:
        log.error("[%s] Email send failed: %s", issue_key, e)


def _md_to_html(raw: str) -> str:
    body = md.markdown(raw, extensions=["tables", "fenced_code"])
    return f"""<!DOCTYPE html>
<html>
<head><style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 820px;
          margin: 2rem auto; color: #1a1a1a; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  th {{ background: #f5f5f5; font-weight: 600; }}
  code {{ background: #f0f0f0; padding: 2px 5px; border-radius: 3px; }}
  pre {{ background: #f0f0f0; padding: 1rem; overflow-x: auto; }}
</style></head>
<body>{body}</body>
</html>"""


def _collect_screenshots(out_dir: str) -> list:
    shots_dir = os.path.join(out_dir, "screenshots")
    attachments = []
    if not os.path.isdir(shots_dir):
        return attachments

    for fname in sorted(os.listdir(shots_dir)):
        if not fname.endswith(".png"):
            continue
        fpath = os.path.join(shots_dir, fname)
        try:
            part = MIMEBase("image", "png")
            with open(fpath, "rb") as f:
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=fname)
            attachments.append(part)
        except OSError as e:
            log.warning("Could not read screenshot %s: %s", fname, e)

    return attachments
