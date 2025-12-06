# web_scraper/emailer.py
import os
import smtplib
from email.message import EmailMessage
import zipfile

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
REPORT_RECIPIENT = os.getenv("REPORT_RECIPIENT", GMAIL_USER)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

def send_file_via_gmail(file_path: str, subject: str, body: str):
    if not GMAIL_USER or not GMAIL_PASS:
        raise RuntimeError("GMAIL_USER / GMAIL_PASS não configurados.")

    zip_path = file_path + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(file_path, arcname=os.path.basename(file_path))

    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = REPORT_RECIPIENT
    msg["Subject"] = subject
    msg.set_content(body)

    with open(zip_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="zip", filename=os.path.basename(zip_path))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(GMAIL_USER, GMAIL_PASS)
        s.send_message(msg)

    os.remove(zip_path)
    return True
